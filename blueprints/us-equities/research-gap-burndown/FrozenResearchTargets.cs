using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;
using QuantConnect;
using QuantConnect.Algorithm;
using QuantConnect.Data;
using QuantConnect.Orders;
using QuantConnect.Orders.Fees;
using QuantConnect.Orders.Fills;
using QuantConnect.Orders.Slippage;
using QuantConnect.Securities;

// Offline integration through vendor portfolio, distribution and fill models.
// Target selection is frozen outside the engine; this is no broker/order adapter.
public class FrozenResearchTargets : QCAlgorithm
{
    private Dictionary<string, Dictionary<string, decimal>> _targets;
    private readonly Dictionary<string, Symbol> _symbols = new();
    private string _ledger;
    private int _decisions;
    private decimal Seconds(DateTime utc) => (utc.Ticks - DateTime.UnixEpoch.Ticks) / 10000000m;
    private void Record(object item) => File.AppendAllText(_ledger, JsonSerializer.Serialize(item) + "\n");

    public override void Initialize()
    {
        if (LiveMode) throw new InvalidOperationException("Offline research replay only.");
        _ledger = GetParameter("ledger");
        _targets = JsonSerializer.Deserialize<Dictionary<string, Dictionary<string, decimal>>>(
            File.ReadAllText(GetParameter("targets")),
            new JsonSerializerOptions { NumberHandling = JsonNumberHandling.AllowReadingFromString });
        SetStartDate(2015, 1, 2);
        SetEndDate(2020, 12, 31);
        SetTimeZone(TimeZones.NewYork);
        SetCash(100000m);
        foreach (var asset in new[] { "SPY", "QQQ", "IWM" })
        {
            var security = AddEquity(asset, Resolution.Daily, fillForward: false,
                extendedMarketHours: false, dataNormalizationMode: DataNormalizationMode.Raw);
            _symbols[asset] = security.Symbol;
            security.SetBuyingPowerModel(new SecurityMarginModel(2m));
            security.SetFeeModel(new ConstantFeeModel(GetParameter("fee-usd", 0m)));
            security.SetSlippageModel(new ConstantSlippageModel(GetParameter("slippage", 0m)));
            security.SetFillModel(new EquityFillModel());
        }
    }

    public override void OnData(Slice data)
    {
        foreach (var dividend in data.Dividends.Values)
            Record(new { kind = "dividend", utc_seconds = Seconds(UtcTime),
                asset = dividend.Symbol.Value, per_share = dividend.Distribution,
                quantity = Portfolio[dividend.Symbol].Quantity,
                amount = dividend.Distribution * Portfolio[dividend.Symbol].Quantity });
        if (data.Splits.Count != 0) throw new InvalidOperationException("Unexpected split in the frozen fixture.");
        if (_symbols.Values.Any(s => !data.Bars.ContainsKey(s))) return;
        var day = data.Bars[_symbols["SPY"]].Time.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
        if (!_targets.TryGetValue(day, out var weights)) return;
        if (weights.Values.Any(w => w < 0m || w > 1m) || weights.Values.Sum() > 1m)
            throw new InvalidOperationException("Frozen research targets must be long-only and unlevered.");
        _decisions++;
        foreach (var asset in _symbols.Keys)
        {
            var symbol = _symbols[asset];
            var weight = weights.TryGetValue(asset, out var value) ? value : 0m;
            var desired = Math.Floor(Portfolio.TotalPortfolioValue * weight * 0.98m / Securities[symbol].Price);
            var quantity = desired - Portfolio[symbol].Quantity;
            if (quantity == 0m) continue;
            var ticket = MarketOnOpenOrder(symbol, quantity, tag: "frozen-target:" + day);
            Record(new { kind = "intent", utc_seconds = Seconds(UtcTime), decision = day,
                asset, order_id = ticket.OrderId, quantity, weight,
                status = ticket.Status.ToString() });
        }
    }

    public override void OnOrderEvent(OrderEvent item)
    {
        // Non-filled events carry upstream OrderFee.Zero, whose currency is
        // deliberately NULL; only an actual nonzero fee needs a USD check.
        if (item.OrderFee.Value.Amount != 0m && item.OrderFee.Value.Currency != "USD")
            throw new InvalidOperationException("Unexpected fee currency.");
        Record(new { kind = "order", utc_seconds = Seconds(item.UtcTime),
            asset = item.Symbol.Value, order_id = item.OrderId, status = item.Status.ToString(),
            quantity = item.FillQuantity, price = item.FillPrice,
            fee = item.OrderFee.Value.Amount, message = item.Message });
    }

    public override void OnEndOfAlgorithm()
    {
        Record(new { kind = "final", utc_seconds = Seconds(UtcTime),
            cash = Portfolio.Cash, equity = Portfolio.TotalPortfolioValue, decisions = _decisions,
            positions = _symbols.ToDictionary(p => p.Key, p => Portfolio[p.Value].Quantity) });
        if (_decisions != _targets.Count || Portfolio.Invested)
            throw new InvalidOperationException("Frozen decisions or terminal flat state did not complete.");
    }
}

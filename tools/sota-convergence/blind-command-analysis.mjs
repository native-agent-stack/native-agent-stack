#!/usr/bin/env node
/** Static command metadata; command text and interpreter payloads are never executed.
 * The existing child-usage loader owns the pinned Bash grammar, runtime and word decoding.
 */
import { readFileSync } from 'node:fs'
import { basename } from 'node:path'
import { pathToFileURL } from 'node:url'
import { loadShellParser, withShellTree, wordValue } from '../../examples/claude-native/workflows/child-usage.mjs'

const SHELLS = new Set(['bash', 'sh', 'dash', 'zsh'])
const EXPANSIONS = new Set(['expansion', 'simple_expansion', 'arithmetic_expansion', 'command_substitution', 'process_substitution', 'brace_expression'])
const UNRESOLVED_STATEMENTS = new Set(['function_definition', 'for_statement', 'c_style_for_statement', 'case_statement', 'test_command', 'declaration_command', 'unset_command', 'arithmetic_command'])
// These commands can execute another utility or source. Their unimplemented argument grammar is not data.
const INDIRECT_PROGRAMS = new Set(['eval', 'source', '.', 'xargs', 'sudo', 'ssh', 'stdbuf', 'flock', 'setsid',
  'chrt', 'taskset', 'ionice', 'parallel', 'watch', 'busybox'])
const OTHER_INTERPRETERS = new Set(['node', 'nodejs', 'ruby', 'perl', 'php', 'lua', 'awk', 'gawk', 'mawk'])
const MAX_SOURCE = 250_000
const MAX_DEPTH = 32
const empty = () => ({ ok: false, errors: [], invocations: [], python_sources: [], shell_regions: [], expansions: [], redirect_paths: [] })
const quote = (value) => "'" + value.replaceAll("'", "'\\''") + "'"
const isPython = (program) => /^(?:python(?:\d+(?:\.\d+)*)?|pypy(?:\d+)?)$/.test(program)

function fields(node, field) {
  return node.children.filter((_, index) => node.fieldNameForChild(index) === field)
}

// Only these small, explicit wrapper forms are interpreted. Other forms remain unresolved.
function wrappedIndex(program, argv) {
  let index = 1
  if (program === 'env') {
    while (index < argv.length) {
      const value = argv[index]
      if (/^[A-Za-z_]\w*=/.test(value) || ['-i', '--ignore-environment', '-0', '--null', '-'].includes(value)) index++
      else if (value === '--') return index + 1
      else if (['-u', '--unset'].includes(value)) index += 2
      else if (value.startsWith('--unset=')) index++
      else if (value.startsWith('-')) return -1
      else return index
    }
    return index
  }
  if (['command', 'builtin', 'exec', 'nohup'].includes(program)) {
    while (index < argv.length && argv[index].startsWith('-')) {
      const value = argv[index++]
      if (value === '--') break
      if (program === 'command' && ['-v', '-V'].includes(value)) return null
      if (program === 'command' && value === '-p') continue
      if (program === 'exec' && ['-c', '-l'].includes(value)) continue
      if (program === 'exec' && value === '-a' && index < argv.length) { index++; continue }
      return -1
    }
    return index
  }
  if (program === 'nice') {
    if (argv[index] === '-n' || argv[index] === '--adjustment') index += 2
    else if (/^--adjustment=|^-\d+$/.test(argv[index] ?? '')) index++
    if (argv[index] === '--') index++
    return argv[index]?.startsWith('-') ? -1 : index
  }
  if (program === 'timeout') {
    while (argv[index]?.startsWith('-')) {
      const value = argv[index++]
      if (value === '--') break
      if (['--preserve-status', '--foreground', '--verbose'].includes(value)) continue
      if (['-s', '--signal', '-k', '--kill-after'].includes(value) && index < argv.length) { index++; continue }
      if (/^--(?:signal|kill-after)=/.test(value)) continue
      return -1
    }
    if (!argv[index]) return -1
    return index + 1 // timeout's duration precedes the utility
  }
  return undefined
}

export function analyzeCommand(text) {
  const result = empty()
  const error = (message) => { if (!result.errors.includes(message)) result.errors.push(message) }
  if (typeof text !== 'string' || text.length > MAX_SOURCE || text.includes('\0')) {
    error('invalid or oversized command source')
    return result
  }
  let visited = 0

  function parse(source, depth = 0, stdin = null) {
    if (depth > MAX_DEPTH || source.length > MAX_SOURCE) { error('command nesting or source limit'); return }
    const parsed = withShellTree(source, (root) => {
      if (root.hasError) { error('Bash grammar parse error'); return }
      function expansion(node) {
        result.expansions.push(node.text)
        error('unresolved shell expansion')
      }
      function redirect(node) {
        if (node.type === 'file_redirect') {
          for (const destination of fields(node, 'destination')) {
            const value = wordValue(destination)
            if (value === null) error('unresolved redirect destination')
            else result.redirect_paths.push(value)
            visit(destination)
          }
        } else if (node.type === 'herestring_redirect') {
          error('here-string interpreter input is unresolved')
          for (const child of node.namedChildren) visit(child)
        }
      }
      function heredoc(node) {
        const start = node.namedChildren.find((child) => child.type === 'heredoc_start')
        const end = node.namedChildren.find((child) => child.type === 'heredoc_end')
        const body = node.namedChildren.find((child) => child.type === 'heredoc_body')
        if (!start || !end || end.endIndex === end.startIndex) { error('unclosed here-document'); return null }
        // The Bash grammar places a piped/conditional tail inside the redirect node. Prefix reparsing alone
        // would lose that command and any interpreter receiving the body. Refuse this unsupported ownership.
        for (const child of node.namedChildren) {
          if (!['heredoc_start', 'heredoc_body', 'heredoc_end', 'file_descriptor'].includes(child.type)) {
            error('here-document command tail is unresolved')
            visit(child)
          }
        }
        const quoted = /['"\\]/.test(start.text)
        const firstLine = source.indexOf('\n', start.endIndex)
        let value = body?.text ?? (firstLine < 0 ? '' : source.slice(firstLine + 1, end.startIndex))
        if (node.children.some((child) => child.type === '<<-')) value = value.replace(/^\t+/gm, '')
        if (!quoted) {
          // Unlike quoted delimiters, the shell expands an unquoted body before the interpreter sees it.
          error('unquoted here-document input is unresolved')
          if (body) for (const child of body.namedChildren) visit(child)
        }
        return { quoted, source: value }
      }
      function invoke(argv, commandSource, input, hops = 0, rawArgv = argv) {
        if (hops > MAX_DEPTH) { error('wrapper nesting limit'); return }
        if (!argv.length || argv[0] === null) { error('unresolved command word'); return }
        const program = basename(argv[0])
        const record = { program, argv, raw_argv: rawArgv, source: commandSource, source_kind: 'argv' }
        result.invocations.push(record)
        // Retain a known program and the raw argument spans for a precise refusal.
        // No wrapper or interpreter decoding may consume an unresolved argument.
        if (argv.some((value) => value === null)) { error('unresolved command word'); return }
        const wrapper = wrappedIndex(program, argv)
        if (wrapper !== undefined) {
          if (wrapper === -1 || wrapper > argv.length) error('unsupported wrapper arguments')
          else if (wrapper !== null && wrapper < argv.length) {
            record.source_kind = 'wrapper'
            record.wrapped_program_index = wrapper
            invoke(argv.slice(wrapper), commandSource, input, hops + 1, rawArgv.slice(wrapper))
          }
          result.shell_regions.push(quote(argv[0]) + ' ' + argv.slice(1, wrapper ?? argv.length).map(quote).join(' '))
          return
        }
        if (SHELLS.has(program)) {
          let codeIndex = -1, noexec = false, readsStdin = true, forceStdin = false
          for (let index = 1; index < argv.length; index++) {
            const value = argv[index]
            if (value === '--') { readsStdin = forceStdin || argv[index + 1] === undefined || argv[index + 1] === '-'; break }
            if (value === '-' || !value.startsWith('-')) { readsStdin = forceStdin || value === '-'; break }
            if (['-o', '-O', '--rcfile', '--init-file'].includes(value)) { index++; continue }
            if (value.startsWith('--')) { error('unsupported shell option'); break }
            if (!/^-[A-Za-z]+$/.test(value)) { error('unsupported shell option'); break }
            noexec ||= value.includes('n')
            forceStdin ||= value.includes('s')
            if (value.includes('c')) { codeIndex = index + 1; break }
          }
          if (codeIndex >= 0) {
            record.source_kind = 'shell_c'
            record.code_arg_index = codeIndex
            if (argv[codeIndex] === undefined) error('missing shell -c source')
            else if (!noexec) parse(argv[codeIndex], depth + 1)
            result.shell_regions.push(argv.filter((_, index) => index !== codeIndex).map(quote).join(' '))
          } else if (input) {
            record.source_kind = 'shell_stdin'
            record.stdin = { language: 'shell', ...input }
            if (input.quoted && !noexec) parse(input.source, depth + 1)
          } else {
            if (readsStdin && !noexec) error('shell stdin source is unresolved')
            result.shell_regions.push(argv.map(quote).join(' '))
          }
          return
        }
        if (isPython(program)) {
          let codeIndex = -1, readsStdin = argv.length === 1
          for (let index = 1; index < argv.length; index++) {
            const value = argv[index]
            if (value === '-c') { codeIndex = index + 1; break }
            if (['-W', '-X'].includes(value)) { index++; continue }
            if (value === '--') { readsStdin = argv[index + 1] === undefined || argv[index + 1] === '-'; break }
            if (value === '-') { readsStdin = true; break }
            if (value === '-m' || !value.startsWith('-')) break
            if (!/^-([bBdEhiIOPqRsSuvVx]+|W.+|X.+)$/.test(value)) { error('unsupported Python option'); break }
          }
          if (codeIndex >= 0) {
            record.source_kind = 'python_c'
            record.code_arg_index = codeIndex
            if (argv[codeIndex] === undefined) error('missing Python -c source')
            else result.python_sources.push(argv[codeIndex])
            result.shell_regions.push(argv.filter((_, index) => index !== codeIndex).map(quote).join(' '))
          } else if (readsStdin && input) {
            record.source_kind = 'python_stdin'
            record.stdin = { language: 'python', ...input }
            if (input.quoted) result.python_sources.push(input.source)
            result.shell_regions.push(argv.map(quote).join(' '))
          } else {
            if (readsStdin) error('Python stdin source is unresolved')
            result.shell_regions.push(argv.map(quote).join(' '))
          }
          return
        }
        if (INDIRECT_PROGRAMS.has(program) || program === 'find' && argv.some((arg) => ['-exec', '-execdir', '-ok', '-okdir'].includes(arg))) {
          error('unsupported command-source indirection')
        }
        if (OTHER_INTERPRETERS.has(program) && (['awk', 'gawk', 'mawk'].includes(program) || argv.slice(1).some((arg) =>
          /^-(?:[a-zA-Z]*[epr]|[epr].*)$/.test(arg) || ['--eval', '--print', '--execute'].includes(arg)))) {
          error('unsupported interpreter source')
        }
        result.shell_regions.push(argv.map(quote).join(' '))
      }
      function command(node, input = stdin) {
        const name = node.childForFieldName('name')
        if (!name?.namedChildCount) { error('missing command name'); return }
        const words = [name.namedChild(0), ...fields(node, 'argument')]
        const argv = words.map(wordValue)
        invoke(argv, node.text, input, 0, words.map((word) => word.text))
        for (const child of node.namedChildren) {
          if (['file_redirect', 'herestring_redirect'].includes(child.type)) redirect(child)
          else visit(child)
        }
      }
      function visit(node) {
        if (++visited > 50_000) { error('command node limit'); return }
        if (node.type === 'command') { command(node); return }
        if (EXPANSIONS.has(node.type)) expansion(node)
        if (['raw_string', 'ansi_c_string', 'comment', 'heredoc_body', 'heredoc_start', 'heredoc_end'].includes(node.type)) return
        if (UNRESOLVED_STATEMENTS.has(node.type)) error('unsupported shell statement: ' + node.type)
        if (node.type === 'redirected_statement') {
          const body = node.childForFieldName('body')
          const redirects = fields(node, 'redirect')
          let input = null
          for (const value of redirects) {
            if (value.type === 'heredoc_redirect') {
              const descriptor = value.childForFieldName('descriptor')
              const feed = heredoc(value)
              if (!descriptor || descriptor.text === '0') input = feed
            } else {
              redirect(value)
              const descriptor = value.childForFieldName('descriptor')
              if ((!descriptor || descriptor.text === '0') && /^\s*</.test(value.text)) input = null
            }
          }
          if (body?.type === 'command' && redirects.length) {
            // The grammar can omit a final '-' before a heredoc. Reparse only the command prefix with the same grammar.
            const prefix = source.slice(node.startIndex, redirects[0].startIndex)
            parse(prefix, depth + 1, input)
          } else {
            if (input) error('compound here-document owner is unresolved')
            if (body) visit(body)
          }
          return
        }
        if (node.type === 'file_redirect' || node.type === 'herestring_redirect') { redirect(node); return }
        if (node.type === 'heredoc_redirect') { heredoc(node); return }
        for (const child of node.namedChildren) visit(child)
      }
      visit(root)
    })
    if (parsed === null) error('verified Bash parser unavailable')
  }
  try { parse(text) } catch { error('Bash analysis failed') }
  for (const key of ['python_sources', 'shell_regions', 'expansions', 'redirect_paths']) result[key] = [...new Set(result[key])]
  result.ok = result.errors.length === 0
  return result
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  let commands
  try {
    const source = readFileSync(0, 'utf8')
    if (source.length > 2_000_000) throw new Error('oversized input')
    commands = JSON.parse(source)
    if (!Array.isArray(commands) || commands.length > 1_000) throw new Error('expected command array')
  } catch {
    process.stderr.write('blind-command-analysis: expected a bounded JSON command array\n')
    process.exitCode = 2
  }
  if (commands) {
    const loaded = await loadShellParser()
    const results = loaded.ok ? commands.map(analyzeCommand) : commands.map(() => ({ ...empty(), errors: ['verified Bash parser unavailable: ' + loaded.reason] }))
    process.stdout.write(JSON.stringify(results) + '\n')
    if (!loaded.ok) process.exitCode = 2
  }
}

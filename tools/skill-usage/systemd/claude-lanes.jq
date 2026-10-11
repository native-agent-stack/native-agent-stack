# Keep only the aggregate skill counts of a child-usage.mjs --lanes-sweep report.
# The full report holds per-actor rows (181 MB for 7 days on 2026-10-11); the
# command-center page reads this projection under its exact policy grant.
{kind, schema_version, window, limits, sessions_in_window, main_sessions_in_window, children_in_window, parse_errors,
 main: (.main | {children, children_with_skill_call, skill_calls}),
 groups: ((.groups | {all, workers, negative_controls} | map_values({children, children_with_skill_call, skill_calls}))
          + {by_agent_type: (.groups.by_agent_type | map_values({children, children_with_skill_call, skill_calls}))})}

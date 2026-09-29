-- Bash calls whose result was an error, over all Bash calls.
SELECT sum(len(list_filter(tool_errors, lambda x: x = 'Bash'))) / nullif(sum(len(list_filter(tools, lambda x: x = 'Bash'))), 0) AS value
FROM turns WHERE in_window(ts);

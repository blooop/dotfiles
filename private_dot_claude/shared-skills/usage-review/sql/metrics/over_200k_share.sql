-- Share of input-side tokens that sit above 200k context in their turn.
SELECT sum(over_200k) / nullif(sum(context), 0) AS value FROM turns WHERE in_window(ts);

# Word swaps

The ASD-STE100 Dictionary — about 900 approved words, each with one part of speech and one
meaning — is the authority, and it is not reproduced here. When a word is not in the table
below, apply its test: **choose the shortest, most common word that a competent engineer
reading English as a second language already knows.** If two candidates tie, pick the one a
dictionary defines without using another long word.

## Longer word → plain word

| Instead of | Write |
| --- | --- |
| utilize, leverage | use |
| prior to | before |
| subsequent to, following | after |
| in order to | to |
| due to the fact that | because |
| in the event that | if |
| is able to, has the ability to | can |
| commence, initiate | start |
| terminate, cease | stop |
| obtain, acquire | get |
| perform, execute, conduct | do |
| ensure, verify | make sure, check |
| indicate | show |
| require | need |
| attempt | try |
| sufficient | enough |
| approximately | about |
| additional | more |
| assist | help |
| modify | change |
| transmit | send |
| receive (a message) | get |
| via | through, with |
| numerous, multiple | many |
| currently, presently | now |
| subsequently | then |
| however | but |
| therefore, thus, hence | so |
| in the vicinity of | near |
| a number of | some, many |
| at this point in time | now |

## Prose habits → plain statement

| Instead of | Write |
| --- | --- |
| X is answerable from Y | you can read X from Y |
| X buys nothing | X does not help |
| X yields Y | X gives Y |
| X strands the wait | the wait never ends |
| X is the honest target | X is the correct state to wait for |
| the gate is spent | the filter turns off after it lets one sample through |
| arm the gate | turn the filter on |
| latch the value | keep the value, record the value |
| it lands at 0.302s | it reads 0.302 seconds |
| non-trivial | large, difficult |
| deterministic | always the same |
| the failure this check exists to catch | the failure this check must find |
| a race | two things that can happen in either order |

The right column is longer in places. That is the trade: more words, less work for the
reader. Sentence length still caps at 25 words — split the sentence rather than reach back
for the compact word.

## Words to keep exactly

A **technical name** is never simplified and never varied:

- identifiers and symbols: `reset_for_restart()`, `SimClockMonitor`, `--headless`
- states and enum members: `RUNNING`, `SimState.SIMULATING`
- file paths and test names, written as markdown links to the repo
- error strings and log lines, quoted verbatim
- protocol and product names: DDS, ROS 2, Bazel, `/clock`

Established domain words also stay, because replacing them makes the text *less* clear to
the reader who has to act on it: *topic*, *subscription*, *poll*, *restart*, *timeout*,
*commit*, *branch*. Define one at first use if the PR's readers might not share it.

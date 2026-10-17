# 0.4.10 bounded runtime observations

Independent profile inheriting 0.4.9. Same recorder settings, acceptance gates, sensor API and ordinary permissions. Adds Date.now duration summaries and at most five contextual spans per metric in the tail constructed at stop; no additional timer, raw sample list or diagnostic file. Head declares the policy. Pending spans at tail construction remain pending, including the final tick. Tail write completion cannot be measured in the tail being written.

This is a diagnostic candidate, not a fix for the native 1.51s callback gap. Host tests cannot establish watch costs, physical continuity or root cause. Clock jumps and instrumentation overhead remain limitations; async write ACK duration is not synchronous blocking time. Old 0.4.9 profile and original exports remain unchanged.

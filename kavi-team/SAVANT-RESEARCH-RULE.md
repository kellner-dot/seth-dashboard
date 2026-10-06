# Standing Rule — Savant-Level Technical Research

**Ordered by Seth, 2026-10-05.** Applies automatically to every future KaviTV, Emby,
Sentinel, server, networking, automation, or playback problem, unless the task is trivial
or time-sensitive enough that deep research would be disproportionate.

## 1. Deep-dive the ecosystem

Before implementing a significant fix or optimization, search broadly across:

- GitHub / GitHub Issues / Discussions
- GitLab
- Codeberg
- Stack Overflow / Stack Exchange
- Reddit and highly relevant niche subreddits
- Hacker News
- Lobsters
- DEV Community
- Hashnode
- Specialized forums
- Discord communities
- Project-specific communities
- Official documentation and issue trackers
- Technical blogs and engineering writeups
- Existing open-source implementations

Different communities contain different kinds of knowledge. GitHub may contain the
implementation, Reddit may contain the workaround, Stack Overflow may contain the exact
failure mode, and a project Discord may contain the undocumented solution.

## 2. Search for the problem, not just the product

Don't only search "How do I fix X?" — also search variations such as:

- "X" workaround / optimization / performance / buffering / latency / timeout
- "X" issue / fix / hack / undocumented / reverse engineering
- "X" alternative implementation / GitHub issue / Reddit / Discord / forum

Look for people who encountered the same problem under a different name.

## 3. Look for the "10x" solution

Don't settle for the first working solution. Ask: is there a substantially better way
someone else has already discovered? Look for clever caching strategies, protocol-level
optimizations, better retry logic, existing libraries, alternative APIs, performance
tricks, undocumented but legitimate capabilities, better architectures, existing
implementations that can be adapted, and failure modes other developers already solved.

## 4. Cross-check before adopting

Community discoveries are leads, not automatically trustworthy facts. For important
changes: Discovery → corroboration → official documentation/source code → controlled
test → implementation. Prefer solutions supported by multiple independent sources or by
directly verifiable source code/documentation.

## 5. Mine old discussions

Don't restrict research to today's posts. Older GitHub issues, Reddit threads, Stack
Exchange answers, forum posts, and Discord discussions can contain solutions that never
made it into official documentation. Search historical discussions whenever the problem
appears unusual or poorly documented.

## 6. Learn from failures

Search specifically for: what didn't work, why it failed, regression reports, performance
complaints, security problems, compatibility issues, people who abandoned an approach.
A failed implementation can be just as valuable as a successful one.

## 7. Apply the knowledge to the architecture

Don't blindly copy a hack. Determine whether the discovered technique belongs in:
KaviTV, Playback Sentinel, Emby integration, TeraBox resolver layer, caching layer,
networking layer, monitoring/telemetry, or build/deployment — then implement it in the
cleanest maintainable location.

## 8. Keep the research trail

For significant fixes, record: problem, what was investigated, communities/resources
searched, important discoveries, candidate solutions, why the selected approach won,
testing/acceptance evidence, known limitations. This prevents the team from
rediscovering the same information later.

## Standing principle

Never assume the obvious solution is the best solution. For every difficult technical
problem: search broadly, search deeply, find the people who already solved something
similar, study their failures as well as their successes, cross-check the discovery,
test it, then implement the best solution — not merely the first solution that works.

The goal is savant-level problem solving, not just competent troubleshooting.

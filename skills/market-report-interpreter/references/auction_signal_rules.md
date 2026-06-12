# Auction Signal Rules

These guardrails prevent text from contradicting numeric facts.

- If `auction_pct <= 0`, do not describe today's behavior as `高开` or `逆势高开`.
- If `auction_pct < -0.3`, today's behavior is a low open. Distinguish `低开强修复`, `低开承接待验证`, and `低开承接失败`.
- If `body_pct <= 0`, do not write `日内转强确认` or `强势反转确认`.
- If `close_pct < auction_pct`, do not write `低开高走`.
- If `CP` is null, do not write `CP高`.
- If `SA` is null, do not write `SA高`.
- If a hard-rule trigger is `post_surge_weak_open_cp`, prefer `强势后弱开兑现风险` over `高开诱多`.
- Every conclusion must cite at least one field from facts.
- Low confidence outputs should use observation language, not decisive language.

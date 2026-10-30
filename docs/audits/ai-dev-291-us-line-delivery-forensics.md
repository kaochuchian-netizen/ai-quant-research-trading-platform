# AI-DEV-291 — US premarket LINE failure forensics

## Scope and evidence

Read-only inspection of production e58086c0a854000a5075ba54ec74abbf9f648159.
Natural run: us-us_pre_market_2000-20261030-200004, Asia/Taipei.
No batch replay, notification, credential read, schedule or production mutation.

Paths below are relative to /home/kaochuchian/stock-ai:

- artifacts/archive/window_snapshots/us/us_pre_market_2000/2026-10-30/revision-0001.json
- artifacts/runtime/us_stock/channel_delivery_receipts/e1addec8b092abdb6b35bece3f653fa5c3f3caf118a0fb6073da36f3e9a800b5.json (Email)
- artifacts/runtime/us_stock/channel_delivery_receipts/4cea3937f200e69982bb8b3e8c6e226a7bbc943c69ddb83a1eab15a22a00ac12.json (LINE)
- artifacts/runtime/us_stock/delivery_provenance/us_pre_market_2000_line_latest.json
- artifacts/runtime/us_stock/delivery_provenance/us_pre_market_2000_email_latest.json
- artifacts/runtime/us_stock/operations_provenance/us_pre_market_2000_latest.json
- artifacts/runtime/us_stock/idempotency/2026-10-30_us_pre_market_2000.json
- artifacts/runtime/us_stock/delivery_status_latest.json
- logs/us_stock/us_pre_market_2000.log

Both receipts identify snapshot c60cf1c10aaead2e2b2633649f468d041f418b4d01ab7ffe071bbdda411baac8,
revision 1, date 2026-10-30, payload hash
553dc8005ea86821f7a175fec2e506e80d6711fe994dcafb9359270de4ff9a0b.

Email: attempted 20:15:18, transport_accepted, accepted_recipient_count=1.
PM independently reports inbox receipt at 20:15. Transport acceptance alone
does not prove inbox delivery.

LINE: attempted 20:15:20, failed, accepted_recipient_count=0, one chunk of 426
UTF-16 units, completed_chunk_count=0, failed_chunk_index=0, error_type=Exception,
partial_delivery_possible=true. Receipt recipient_count=1 is an unresolved
transport placeholder, not proof of one configured recipient. No recipient
identity is reproduced here. Provenance says attempted=true, result=failed;
idempotency confirms both channels attempted. No evidence of suppression.

## Root cause and limits

LINE_RESULT=FAILED. The exact provider HTTP status/reason for this run is UNKNOWN:
the exception is reduced to its type and the failed wrapper retains only a
stdout tail. The prior 2026-10-29 log contains HTTP 429/monthly-limit text, but
that is not proof of the 2026-10-30 response. No token, permission, recipient,
or quota change is justified solely by this evidence. Stderr contains only
shadow-evaluation PENDING and a Playwright host-validation notice.

Confirmed code defects: a worker returning a valid partial-delivery result
exits 2; the parent overwrites it with failed_closed and both channels
not_attempted. The sender exception loses HTTP diagnostics before receipt
persistence; provenance omits receipt linkage despite an existing receipt.

## Fix and validation boundary

Preserve structurally consistent completed worker results on exit 2 while
keeping ok=false. Keep malformed, wrong-window and signal failures fail-closed.
Persist only numeric HTTP codes and allowlisted reasons through chunk evidence;
never persist raw sender exception text. Wire immutable receipts to provenance.
No automatic retry, historical receipt rewrite or production deployment.

Regression tests are synthetic evidence for the fix, not formal delivery proof.
Natural verification remains pending after review and separately approved deployment.

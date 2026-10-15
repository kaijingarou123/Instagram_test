# Instagram API Posting Limits & New-Account Safety — Research Report

*Compiled 2026-10-15 for an automated wildlife/nature-education account (new Business/Creator account, 0 followers, publishing via Instagram Graph API content_publishing through Composio). Priority: never get banned, shadowbanned or rate-limited.*

Source tiers: **[OFFICIAL]** = Meta developer docs / Instagram Help Center / Instagram creators site. **[PRESS]** = reputable tech press. **[COMMUNITY]** = vendor blogs, forums; treat numbers as heuristics, not rules.

---

## 1. Official Graph API content-publishing limits

| Item | Value | Source |
|---|---|---|
| API-published posts per rolling 24 h | **50 per `content_publishing_limit` reference (`quota_total: 50`, `quota_duration: 86400`)**; the Content Publishing guide now says **100** in its Rate Limit section but still says **50** in its carousel section | [OFFICIAL] [content_publishing_limit ref](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/content_publishing_limit); [Content Publishing guide](https://developers.facebook.com/docs/instagram-platform/content-publishing) |
| Where enforced | `POST /<IG_ID>/media_publish` (container creation is not what's counted) | [OFFICIAL] same guide |
| Carousels | Count as **one** post regardless of child count | [OFFICIAL] same guide |
| Reels / Stories | Docs never state they are exempt; they are published through the same `media_publish` endpoint and the quota counts "IG Containers published", so **assume they count**. Third-party vendors state they share the same pool. | [OFFICIAL] ref above; [COMMUNITY] [rapidevelopers](https://rapidevelopers.com/api-automations/how-to-automate-instagram-reels-scheduling-using-the-api) |
| Usage check | `GET /<IG_ID>/content_publishing_limit?fields=quota_usage,config` (optional `since`, max 24 h back). Meta recommends apps enforce the limit themselves, especially for scheduled posts. | [OFFICIAL] ref above |
| Container lifetime | Unpublished container expires after 24 h; poll `status_code` once per minute, max 5 min; publish only when `FINISHED` | [OFFICIAL] guide |
| Caption limits | 2,200 chars, **30 hashtags**, 20 @-mentions (error 2207010 / 2207040) | [OFFICIAL] [Error codes](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/error-codes) |
| General call rate | Instagram Platform BUC limit: calls per 24 h = 4800 × impressions in last 24 h (per app+user). Platform app limit 200 × users per hour. Headers `X-App-Usage`, `X-Business-Use-Case-Usage` (`type: instagram`, `estimated_time_to_regain_access`). Codes 4, 17, 32, 613, 80002. | [OFFICIAL] [Rate limiting](https://developers.facebook.com/docs/graph-api/overview/rate-limiting) |

**Confidence note (50 vs 100):** Meta's own pages conflict. The machine-readable reference says 50; the narrative guide was partly updated to 100. Do not hardcode either — read `config.quota_total` live and stay far below it. For this project the difference is academic (we will post ≤2/day).

**Important for a 0-follower account:** the BUC call budget is `4800 × impressions`. With zero impressions the formula yields a tiny budget; Meta does not publish a floor. Keep API calls minimal (one `content_publishing_limit` check, one container create, ≤5 status polls, one publish per post) and back off on any code 4/17/613/80002.

## 2. Media requirements for API publishing

All [OFFICIAL] from the [IG User Media reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media) and the Content Publishing guide unless noted.

**Images (feed & carousel children)**
- Format: **JPEG only** (MPO/JPS unsupported; PNG/WebP/HEIC fail with 2207005).
- Max file size **8 MB** (error 2207004 says "less than 8 MiB").
- Aspect ratio **4:5 (0.8) to 1.91:1** (error 2207009 otherwise). Carousel children are cropped to the first child's ratio (default 1:1).
- Width **320–1440 px** (scaled otherwise); sRGB (others converted).
- `alt_text` supported on image posts since 2025-03-24 (not Reels/Stories) — use it, it is an accessibility/originality signal.

**Carousels**
- **2–10 items** (error 2207028 outside range), images, videos or a mix. Reels cannot be children. Caption/location only at carousel level.

**Reels (`media_type=REELS`)**
- Container MOV or MP4, no edit lists, **moov atom at front** (faststart).
- Video: H.264 or HEVC, progressive, closed GOP, 4:2:0. **23–60 fps**. Max **1920 px** wide. Aspect 0.01:1–10:1 allowed, **9:16 recommended**. VBR ≤25 Mbps.
- Audio: AAC, ≤48 kHz, mono/stereo, 128 kbps. (Audio track optional.)
- Duration **3 s – 15 min**. File **≤300 MB**. Cover JPEG ≤8 MB, 9:16 (center-cropped otherwise).
- Since July 2023 all single feed videos published via API are shared as Reels.

**Stories (`media_type=STORIES`)**
- Image: JPEG ≤8 MB, 9:16 recommended. Video: same codecs as Reels, **3–60 s**, ≤100 MB, 9:16 recommended.

**Hosting**
- "We cURL media used in publishing attempts, so the media must be hosted on a publicly accessible server at the time of the attempt." URLs should be plain US-ASCII. Container not published within 24 h expires.
- Resumable upload (local files) exists **only for Facebook-Login apps**, not Instagram-Login apps.
- Known failure modes: 2207003 (download timeout), 2207052 ("could not be fetched from this uri"), 2207004 (too large).
- **GitHub raw URLs:** no official statement and no definitive community thread found. Community reports ([n8n forum](https://community.n8n.io/t/instagram-facebook-graph-api-google-drive-links-are-no-longer-accepted-resolved/165635)) show that Google Drive share links stopped working because Meta requires a direct file URL with no redirects, no auth tokens, no HTML wrapper. `raw.githubusercontent.com` serves direct bytes but with `Content-Type: text/plain` for some files and is throttled; it is **unverified** — test with `curl -I` (expect 200, `image/jpeg`, no 3xx) and a real container before relying on it. Prefer a CDN/object store (S3/R2/Cloudinary) with correct `Content-Type`. **[COMMUNITY, low confidence]**

## 3. Account requirements

[OFFICIAL] [Instagram Platform overview](https://developers.facebook.com/docs/instagram-platform/overview); [Instagram-Login content publishing](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing); [Insights ref](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/insights).

- Must be an Instagram **professional** account — **Business or Creator both work**; personal accounts cannot publish via API.
- **Instagram API with Instagram Login** (`graph.instagram.com`, Business Login for Instagram): **no Facebook Page required**. Permissions `instagram_business_basic` + `instagram_business_content_publish`. No hashtag search, no product tagging, no partnership ads, **no resumable upload**.
- **Instagram API with Facebook Login** (`graph.facebook.com`): requires a **linked Facebook Page** the user admins. Permissions `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`. Adds resumable upload, hashtag search, etc. Pages needing Page Publishing Authorization cannot publish until completed.
- App must be a **Business**-type Meta app. Standard Access suffices for accounts you own/manage; Advanced Access (App Review + Business Verification) only if serving third-party accounts.
- Insights thresholds: `follower_count`, `online_followers`, `follows_and_unfollows`, `follower_demographics` need **≥100 followers**; `engaged_audience_demographics` needs ≥100 engagements in the window. `impressions` deprecated since 2025-04-21. Data can lag 48 h.

## 4. New-account safety

### 4a. Cadence (all [COMMUNITY]; Instagram publishes no warm-up numbers)
Sources: [shadowphone 14-day plan](https://www.shadowphone.io/blog/instagram-account-warm-up-guide-2026), [superscale](https://superscale.ai/learn/the-right-way-to-warm-up-new-tiktok-instagram-accounts/), [IPFoxy 21-day](https://www.ipfoxy.com/blog/ideas-inspiration/5476), [multilogin](https://multilogin.com/blog/how-to-warm-up-accounts/), [contentstudio shadowban guide](https://contentstudio.io/blog/instagram-shadowban), [later.com](https://later.com/blog/instagram-shadowban/). Several of these sell multi-account/proxy tooling; ignore that part.
- Consensus: days 1–3 complete profile (photo, bio, name), 0–1 post, some manual browsing/follows from the app; days 4–7 ≤1 post/day; week 2 1–2 posts/day + 1–2 stories; week 3+ "regular" cadence. Some suggest only 2–3 posts/week for the first two weeks. "Following 50 accounts on day one is a massive red flag." No bio link for ~2 weeks.
- Zero-follower accounts posting many times per day via API look like spam farms; the risk is not the API quota but Instagram's integrity classifiers.
- Suggested hard ceilings from vendors: ≤10–15 actions/hour early on; stop all activity 48–72 h if Account Status shows a restriction.

### 4b. Behaviours that trigger automation/spam flags ([COMMUNITY] unless noted)
- Posting bursts (several posts within minutes), identical or near-identical captions, the same hashtag block on every post, hashtag stuffing, generic/irrelevant tags, link-in-caption to low-trust domains, repetitive comments/DMs, follow/unfollow churn, logins from many IPs, any third-party tool that logs in with credentials ([interakt](https://www.interakt.shop/instagram-automation/avoiding-spam-flags/), [upgrow](https://www.upgrow.com/blog/avoid-instagram-bans-risk-free-automation-tips)).
- [OFFICIAL] Error 4/2207051 "We restrict certain activity to protect our community" = Instagram treated the publish as possible spam. Error 25/2207050 "The Instagram account is restricted" = must log into the app and complete checks.
- [OFFICIAL] Meta's Spam policy and Instagram Community Guidelines prohibit spam but do not publish detection signals ([transparency.meta.com](https://transparency.meta.com/policies/)).

### 4c. Hashtags
- [PRESS, citing Instagram] Dec 18 2025: Instagram is **limiting captions to 5 hashtags** for posts and Reels (after testing 3). Instagram: "using fewer (up to 5) more targeted hashtags" improves performance. Mosseri (Feb & May 2025): hashtags "don't work" for reach but are "a great way to let people know what a post is about" ([Social Media Today](https://www.socialmediatoday.com/news/instagram-implements-new-limits-on-hashtag-use/808309/)). The older @creators "3–5 hashtags" guidance is consistent ([Flick](https://flick.social/learn/blog/post/3-5-hashtags-on-instagram)).
- [OFFICIAL] API still technically accepts 30, but using more than 5 contradicts current product guidance and may be rejected as the rollout completes.
- **Banned/restricted tags:** no authoritative 2025–26 list exists; blog lists are stale. Generic tags like #nature, #wildlife, #animals are not banned but are useless for reach. Since 2017 Instagram shows a wildlife-exploitation warning on hundreds of unpublished tags such as #koalaselfie, #slothselfie, #monkeyselfie, #lionselfie, #tigerpet, #exoticanimalforsale, #koalahugs ([Gizmodo](https://gizmodo.com/instagram-is-warning-users-that-cute-exotic-animal-se-1821010576), [Inverse](https://www.inverse.com/article/39009-instagram-illegal-animals-selfies-hashtags-wildlife)). Avoid any tag combining an animal with selfie/pet/forsale/cuddle. Before using a tag, search it in the app; if it shows a warning or "posts hidden", drop it ([COMMUNITY]).

### 4d. Recommendation Guidelines & originality (critical for CC-licensed media)
[OFFICIAL] [Original Content Guidelines](https://creators.instagram.com/original-content-guidelines/), [Rewarding original creators (2026-04-30)](https://creators.instagram.com/blog/rewarding-original-creators-on-instagram), [Recommendations Guidelines](https://help.instagram.com/313829416281232), [Account Status](https://help.instagram.com/653964212890722). Press: [Engadget](https://engadget.com/2160560/instagrams-recommendation-algorithm-will-penalize-unoriginal-photo-and-carousel-posts), [PetaPixel](https://petapixel.com/2026/04/30/new-instagram-policies-target-reposted-content/).
- 2024: Reels aggregators (10+ unoriginal reposts in 30 days) removed from recommendations. **April 30 2026: extended to photos and carousels.** Test is now "if your account primarily posts unoriginal reels, photos, or carousels you didn't create or edit in a material way, your account may not be seen in recommendations to new audiences." Rolling 30-day window; eligibility returns "when most of your recently posted reels, photos, and carousels are considered original in a 30-day period."
- Effect: loss of Explore/Reels-tab/suggested distribution (followers still see posts). For a 0-follower account that is effectively zero reach. Checkable and appealable in **Account Status**.
- **Does NOT count as original:** exact reposts; screenshots "even if you credit the original creator"; borders, watermarks, speed changes, subtitles, caption credit, cropping/resizing; "simply adding a different caption or superficial elements."
- **Counts as original:** "material edits to third-party content … when your addition meaningfully enhances the content." Examples Instagram gives: unique overlaid text that "offers more information than the original" (not just describing the scene), narration, a storyline, creative graphics that add new information, Remix. Test: "if someone could remove your contribution and the content would virtually be the same, it probably needs more of you in it."
- Recommendations Guidelines separately list "unoriginal content that is largely repurposed from another source without adding material value", engagement bait, and clickbait as non-recommendable. Content with visible third-party app watermarks (e.g. TikTok) is also deprioritised (widely reported; [COMMUNITY/PRESS]).
- Note: the originality system is primarily aimed at content copied *from other Instagram users*; Instagram says it tries to surface the original poster. CC photos from Wikimedia/Pexels are mostly not on Instagram, so match risk is lower — but the "primarily reposts" classifier is content-based, so **every post must carry substantial added educational value baked into the media itself** (designed card, overlaid facts, narration), not just a caption.

## 5. Copyright & licensing

| Source | Licence | Attribution | Social-media safe? |
|---|---|---|---|
| Wikimedia Commons CC-BY / CC-BY-SA | Attribution (+ShareAlike) | **Required**: author, licence name+version, link to source ([Wikimedia Legal](https://meta.wikimedia.org/wiki/Legal/CC_BY-SA_licenses_and_social_media/en), [Creative Commons](https://creativecommons.org/2020/06/15/sharing-openly-licensed-content-on-social-media/)) | Yes. Wikimedia Legal says attribution "in the same post" (caption) with a link to the Commons file page satisfies the licence; a small credit baked into the image is best practice. CC-BY-SA adaptations must stay BY-SA — say so in caption. Instagram's ToS grants Meta a licence to your upload; Wikimedia/CC treat this as compatible in practice but **[contested; moderate confidence]** — prefer CC-BY and PD over BY-SA where possible. |
| Public domain / CC0 | None | Not required (credit anyway) | Yes |
| CC-BY-NC / NC-ND | NonCommercial | Required | **Avoid** — a Business account is arguably commercial ([CC blog](https://creativecommons.org/2020/06/15/sharing-openly-licensed-content-on-social-media/)) |
| Pexels | Pexels License | "Attribution is not required" | Yes — licence page explicitly encourages Instagram use; no selling unaltered copies, no implied endorsement ([pexels.com/license](https://www.pexels.com/license/)) |
| Unsplash | Unsplash License | Not required | Yes; no selling unmodified, no compiling a competing library ([unsplash.com/license](https://unsplash.com/license)); Unsplash+ paid content has extra limits |
| Pixabay | Pixabay Content License (not CC0 since 2019) | Not required | Yes for use inside a post; cannot distribute "on a Standalone basis" (no creative effort applied) — so add overlay/edit ([pixabay license summary](https://pixabay.com/service/license-summary/)) |

- Always record for each asset: source URL, author, licence+version, download date (licence terms change; Pexels/Pixabay still hold legacy CC0 items).
- Model/trademark/property rights are not cleared by any of these licences; wildlife content rarely has this issue but avoid images with people, logos, zoo branding.
- **Rights Manager / audio:** Meta's Rights Manager fingerprints video and audio in rights-holders' reference libraries and auto-blocks/mutes/claims matches on Facebook and Instagram ([rightsmanager.fb.com](https://www.rightsmanager.fb.com)); false matches on licensed, public-domain or stock material happen and must be disputed ([Vondran](https://www.vondranlegal.com/meta-rights-manager-explained)). Business accounts don't get the main licensed music library; only Meta Sound Collection or your own licensed audio ([help.instagram.com](https://help.instagram.com/ipad-app/402084904469945)). API-published Reels with embedded copyrighted audio are muted or blocked ([COMMUNITY]). **Rule: Reels with no audio track, or audio you verifiably own/CC0, or Meta Sound Collection. Never "royalty-free" tracks from unknown YouTube channels.** Stock *footage* from Pexels/Pixabay has low Rights Manager risk but non-zero (other users may have registered compilations); keep the licence record for disputes.

## 6. Posting times & frequency (2025–26, brief)
[COMMUNITY/data studies] [Buffer 9.6M posts](https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram): Wed/Thu best; Thu 9 am, Wed 12 pm, Wed 6 pm. [Metricool 24M posts](https://metricool.com/best-time-to-post-instagram/): 6–9 pm peak. [Sociality.io](https://sociality.io/blog/best-time-to-post-on-instagram/): 8 pm–midnight. Studies disagree; use audience local time and, once >100 followers, `online_followers` insights. Frequency: [SocialPilot](https://www.socialpilot.co/instagram-marketing/how-often-to-post-on-instagram) 3–5 posts/week; [DashSocial](https://www.dashsocial.com/blog/how-often-should-you-post-on-instagram) 2–3 Reels/week highest engagement; Mosseri's historic guidance "a couple feed posts a week, and a couple stories a day." No educational-niche-specific study found.

---

## Recommended safe operating envelope

**Weeks 1–2 (days 1–14)** — *manual-first warm-up*
- Days 1–3: complete profile in the app by hand (photo, name, bio, category, no external link). Publish the first 1–2 posts **manually from the app**, not the API. Follow ≤5–10 relevant accounts/day by hand.
- Days 4–14: **max 1 API post/day**, ≥20 h between posts, never two in the same 6-h window. Feed images or carousels only (no Reels yet; Reels get heaviest originality scrutiny). 0–1 story/day, manual. Total ≤7 posts/week.
- No bio link, no links in captions, no @-mentions of accounts you don't know.

**Weeks 3–4**
- **Max 2 posts/day**, ≥8 h apart; typical 1/day. Add ≤2 Reels/week (no audio or Sound Collection). Stories ≤2/day.
- Post at varied times inside a 6–9 pm or 9 am–12 pm local window; jitter publish time ±45 min.

**After week 4 (if Account Status is clean)**
- Ceiling **3 posts/day**, ≥6 h apart; recommended 1 post/day + 2–3 Reels/week + 1–2 stories/day. Never exceed **10 API publishes/day** even though the quota is 50/100.
- Check `content_publishing_limit` before every publish; halt if `quota_usage ≥ 20`.

**Hashtags & captions (all phases)**
- **3–5 hashtags**, all specific (species, region, behaviour, e.g. #snowleopard #himalayanwildlife #conservationeducation); rotate from a pool of ≥40; max 2 tags shared with the previous post; never the same set twice in a row. No animal+selfie/pet/forsale tags.
- Captions unique per post: Jaccard similarity of word sets vs the last 30 captions <0.5; vary opening sentence structure; ≤1,500 chars; always include CC attribution block (`Photo: <Author>, <Licence> <version>, via Wikimedia Commons <file URL>`) and the educational body; 1 CTA max; no external links.
- Set `alt_text` on every image.

**Originality rules (every post)**
- Media must be a *designed* asset: CC photo + overlaid species facts/map/infographic/title card, or a carousel mixing photo + text slides; Reels with narration/captions overlaid. Never upload the raw CC file. No third-party watermarks/logos; our own small credit line is fine.
- Keep a licence ledger (source URL, author, licence, date, edits made). Prefer PD/CC0/CC-BY; CC-BY-SA acceptable with licence stated; **no NC/ND**.

**Media validation before upload**
- Image: JPEG, sRGB, 1080×1350 (4:5) or 1080×1080, ≤8 MB (target <2 MB), aspect in [0.8, 1.91]. Carousel 2–10 items, all same aspect.
- Reel: MP4 H.264 + AAC (or no audio), faststart/moov-front, 1080×1920, 30 fps, 5–90 s (API allows 3 s–15 min), ≤100 MB, ≤25 Mbps.
- Hosting: direct HTTPS URL, `curl -I` returns 200, correct `Content-Type` (`image/jpeg`/`video/mp4`), no redirects, no query tokens, ASCII path; keep live ≥1 h after publish. Test GitHub raw once in a sandbox before trusting it; prefer S3/R2.
- Flow: `content_publishing_limit` → create container → poll `status_code` ≤5×/1 min → publish only on `FINISHED` → verify media ID. Create and publish in the same run.

**Hard-stop conditions (halt automation, alert human, no retries)**
- Error **4 / 2207051** "We restrict certain activity to protect our community" (spam classification).
- Error **25 / 2207050** "The Instagram account is restricted".
- Error **9 / 2207042** daily publishing limit reached (should never happen at our cadence — indicates a bug/loop).
- Error **4, 17, 613 (esp. subcode 1996), 80002**, or `X-Business-Use-Case-Usage.estimated_time_to_regain_access > 0` → stop for at least that many minutes + 24 h.
- Error **190** / any OAuth or token-expiry error (user must re-auth in app; could mean a checkpoint).
- Two consecutive media failures (2207003/2207052/2207004/2207005/2207009) → stop and fix pipeline, don't loop.
- Account Status (in-app) shows any "not eligible for recommendation", "removed content" or "restricted feature" — pause 72 h, review, appeal if wrong.
- Any post removed, hashtag warning, or sudden reach drop to zero on 3 consecutive posts.
- Only safe retry: `-1 / 2207001`, `2207032`, `2207053`, `9007 / 2207027` — once, after 60 s.

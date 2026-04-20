# Brevard ROD â€” Initial Recon Dossier (v1)

**Target:** Brevard County (FL) Clerk of the Court & Comptroller â€” Official Records Search (public indexed ROD + images 1981â†’present)
**Use case:** BidDeed.AI / Everest programmatic lookup of liens, deeds, mortgages, assignments, satisfactions, and other Official Record instruments tied to parcels under foreclosure / tax-deed pipelines.
**Recon date:** 2026-04-20
**Recon method:** Chat-driven web_search + web_fetch (Hetzner runner blocked by expired Max OAuth; see `dossiers/runner-fix/RUNNER-FIX-V2.md`).
**Status:** V1 â€” initial surface map. Network-layer request/response schemas UNTESTED; require a live browser or headless-browser pass.

---

## 1. Endpoint

| Field | Value |
|---|---|
| Public base URL | `https://vaclmweb1.brevardclerk.us/AcclaimWeb/` |
| Vendor platform | Acclaim Web by **Harris Recording Solutions** (a Harris Computer Systems business unit; product originally developed by Aptitude Solutions Inc.) |
| Product family | Same Acclaim codebase is deployed at many county recorders (Horry SC, Grand CO, Hudson NJ, Hamilton OH, etc.) â€” recon findings here are reusable per-county with base-URL swap. |
| Canonical entry | `https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/Disclaimer?st=/AcclaimWeb/search/SearchTypeName` â€” presents disclaimer gate, then routes to selected search type. |
| Framework | ASP.NET MVC (`/search/SearchType*` controller routes, ASP.NET forms-style paths). |
| Required client features | JavaScript AND cookies. The disclaimer page explicitly blocks non-JS clients and non-cookie clients (literal text: "You must enable Javascript to continue" / "You must enable Cookies to continue"). Direct `curl`/`requests` against the search pages returns either the disclaimer or times out. |
| TLS | HTTPS only (server returns on 443). TLS handshake completes normally; public CA. |
| Related static site | `https://www.brevardclerk.us/official-records` â€” informational landing page with links to AcclaimWeb, image subscription form, and contact info. |

### Nine search types enumerated from navigation

All are routes under `https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/`:

| Search type | Path | Likely inputs (per vendor docs) |
|---|---|---|
| Name (party) | `/search/SearchTypeName` | Last name, first name, direct/reverse flag, date range, doc type filter |
| Book / Page | `/search/SearchTypeBookPage` | Book number, page number |
| Document Type | `/search/SearchTypeDocType` | Doc-type code (DEED, MTG, LIS PEN, etc.), date range |
| Clerk File Number (Instrument Number) | `/search/SearchTypeInstrumentNumber` | CFN / instrument number string |
| Record Date | `/search/SearchTypeRecordDate` | Single record-date (per vendor: "single day" scope), optionally filtered by doc type |
| Case Number | `/search/SearchTypeCaseNumber` | Case number string (ties to court cases, foreclosure LP filings) |
| Consideration | `/search/SearchTypeConsideration` | Lower + upper consideration bounds (dollars); targets conveyance docs |
| Doc Legal | `/search/SearchTypeDocLegal` | Legal-description text search (subdivision, township, range, section, etc.) |
| Simple Search | `/search/SearchTypeSimpleSearch` | Free-text / natural-language guided search ("I need a copy of my Deed", "Are there any liens filed against me") |

### Coverage

- Index data: **1981-01-01 â†’ present** ([VERIFIED] from brevardclerk.us/official-records page).
- Images: same 1981-01-01 â†’ present, for statutorily imageable records.
- Image *viewing* in the browser via AcclaimWeb is public for most indexed records. Bulk / watermark-free / printable image access requires a separate **Official Records View** subscription (paid; form at `https://www.brevardclerk.us/official-records-view`).

---

## 2. Request schema [UNTESTED]

**Direct-inspection of the POST bodies requires a browser with devtools or a headless browser driver (Playwright / Puppeteer / Firecrawl). `web_fetch` alone cannot observe the XHR traffic that AcclaimWeb uses after the user clicks Search.**

Best-guess shape (based on Acclaim's public behavior at sibling counties and the ASP.NET MVC route naming):

```
Likely per-search-type flow:
  1. GET  /AcclaimWeb/search/Disclaimer?st=/AcclaimWeb/search/SearchType{X}
     -> renders disclaimer, sets initial __RequestVerificationToken cookie + hidden field
     -> user accepts disclaimer (POST back with token)
  2. GET  /AcclaimWeb/search/SearchType{X}
     -> renders form HTML, includes __RequestVerificationToken hidden field
  3. POST /AcclaimWeb/search/SearchType{X}        (or sibling JSON endpoint like /Search/...)
     Content-Type: application/x-www-form-urlencoded  OR  application/json
     Required headers:
       Cookie: ASP.NET_SessionId=...; __RequestVerificationToken=...; AcclaimWebAuth=... (possibly)
       __RequestVerificationToken: <hidden-field-value>
     Likely body fields per search type:
       SearchTypeName:           LastName, FirstName, SearchDirection (forward|reverse|both),
                                 RecordDateFrom, RecordDateTo, DocTypesList[], PartyType
       SearchTypeBookPage:       Book, Page
       SearchTypeDocType:        DocTypes[], RecordDateFrom, RecordDateTo
       SearchTypeInstrumentNumber: InstrumentNumber  (aka CFN)
       SearchTypeRecordDate:     RecordDate  (single date)
       SearchTypeCaseNumber:     CaseNumber
       SearchTypeConsideration:  ConsiderationLow, ConsiderationHigh, RecordDateFrom, RecordDateTo
       SearchTypeDocLegal:       Subdivision, Block, Lot, Section, Township, Range
       SearchTypeSimpleSearch:   <guided-mode variant, builds one of the above>
```

**ALL field names above are INFERRED from (a) the search-type navigation labels on the AcclaimWeb disclaimer page, (b) Harris Recording Solutions / Aptitude Solutions vendor documentation at other county AcclaimWeb deployments, and (c) the standard ASP.NET MVC antiforgery-token pattern. Exact field names, casing, and serialization MUST be verified against a real browser capture in the next recon pass.**

### Antiforgery / session expectations

- ASP.NET MVC apps of this vintage typically pair a cookie `__RequestVerificationToken` with a hidden form field of the same name. Submitting without the matched pair returns HTTP 500 or a redirect to the disclaimer.
- A session cookie (likely `ASP.NET_SessionId`) ties the accepted-disclaimer flag to session. Scrapers must POST the disclaimer-accept action before the session is considered valid for search.

---

## 3. Response schema [UNTESTED]

Per the vendor user guide at the Horry SC AcclaimWeb deployment (same codebase): *"Once you complete a search, the results matching the criteria you selected appear in a table."*

**Expected result columns** (inferred from the sibling-county UI and standard recording-index shape):

- Record Date
- Doc Type (3-5 char code)
- Book / Page OR Clerk File Number (CFN)
- Party 1 (Grantor) / Party 2 (Grantee) â€” shown per-indexed-name
- Consideration (for conveyance docs)
- Legal Description (truncated, link to full detail)
- Link to Document Detail view
- Link to Image viewer (if subscribed / if public)

Result transport format: likely server-rendered HTML table via partial view, OR JSON returned to a client-side grid control (DataTables / Kendo Grid / vendor-custom). **TBD on inspection.**

Pagination: likely standard page-size + page-number query params, OR infinite-scroll AJAX â€” unknown.

---

## 4. Auth and session

- **No user account required** for the public search.
- **Disclaimer acceptance is mandatory** and session-scoped. A fresh session must POST the disclaimer-accept action before any search endpoint returns data.
- **JavaScript is mandatory**. The disclaimer page explicitly blocks non-JS UAs.
- **Cookies are mandatory**. Disabled cookies trigger the same blocking message.
-
Š’[XYÙHšY]Ú[™ÊŠˆ8 %H
˜œ›İÜÙXX›Jˆ[‹X\[XYÙHšY]Ù\ˆ\ÈX›XÈ›Üˆ[ÜİØÜËˆ
‘İÛ›ØYX›HÈš[X›HÈ[Êˆ[XYÙHXØÙ\ÜÈ™\]Z\™\ÈHZYÙ™šXÚX[™XÛÜ™ÈšY]ÈİXœØÜš\[Ûˆ
ÙYHœ™]˜\™Û\šË\ËÛÙ™šXÚX[\™XÛÜ™Ë]šY]Ø8 %İXœØÜš\[Ûˆ›Ü›KÛÛXİXØÛZ[]\Ù\˜YZ[œ™]˜\™Û\šË\Ø
ÌŒJHŒÍËLŒ
K‚‹H
Š[ÈÈÛÛ[Y\˜ÚX[]JŠˆ›ÈX›XÈ[ËYİÛ›ØY•ÈÌÈÈ]KY™YY\È™Y[ˆY[YšYYˆ›Üˆ[È[™Ù\İ[Û‹]™\™\İÚİ[ÛÛXİHÛ\šÉÜÈÙ™šXÙH\™XİH
XØÛZ[]\Ù\˜YZ[œ™]˜\™Û\šË\ËÙ™šXÚX[™XÛÜ™Ò[XYÙT™\]Y\İĞœ™]˜\™Û\šË\ÊHÈ\Øİ\ÜÈH]K\Ú\š[™ÈÈİXœØÜš\[Ûˆ\œ˜[™Ù[Y[‚‹H
Š•\Ù\‹XYÙ[ÈT›ØÚÚ[™ÊŠˆ[˜ÛÛ™š\›YY]›Ø˜X›H]H\XØ][ÛˆY\‹ˆØÜ˜\\œÈ][[Y\ˆÚ]İ]™X[\İXÈœ›İÜÙ\ˆš[™Ù\œš[È\™HZÙ[HÈ]ÛÙ›ØÚÜËˆHÙX—Ù™]Ú™XY][Y[İ]È\š[™È\È™XÛÛˆÛˆĞXØÛZ[UÙX‹Ø[™HÙX\˜Ú]\HYÙ\È
Ú[HHÑ\ØÛZ[Y\˜YÙH™]\›™Yš[™JH\™HÙXZÛHÛÛœÚ\İ[Ú]™Z]š[Ü˜[š[™Ù\œš[[™ËİYÚÛİ[[ÛÈ™HZ[ˆ”Ë\™[™\š[™È[Y[İ]ÈÛˆHÛİÈŞ[˜Ú›Û›İ\È[™Ú[‚‚‹KKB‚ˆÈÈKˆ˜]H[Z]È[™]\]Y]B‚‹H
Š“›ÈX›\ÚY˜]H[Z]ËŠŠˆÚ\™YÛİ[H[™œ˜\İXİ\™H8 %[[Y\š[™ÈÚ[™H›İXÙY‚‹H
Š‘Ù[HY˜][È›ÜˆŒHY\\ŠŠ‚ˆHX^H™\]Y\İ]™\H‹LÈÙXÛÛ™Èœ›ÛH[HÚ[™ÛHTÚ]š]\‹‚ˆH™\ÜXİ™]KPY\˜Ûˆ[HHÈLË‚ˆH˜XÚÈÙ™ˆ^Û™[X[HÛˆ^‚ˆHY[YHHØÜ˜\\ˆÛ™\İH[ˆH\Ù\‹PYÙ[Ú[ˆ\ÈØ[ˆ™HÛ™HÚ]İ]š\[™ÈH\	ÜÈPKYš[\ˆ
K™Ë‹]™\™\İPØ\][UTĞHšYYYRKÌKŒ
ÛÛXİ\šY[]™\™\İØ\][\ØK˜ÛÛJX
K‚‹H
Š”™Y™\œ™Y\›ØXÚŠŠˆØXÚHYÙÜ™\ÜÚ]™[KˆH“Ñ[™^\È\[™[Û›H8 %\İÜšXØ[™XÛÜ™ÈÈ›İÚ[™ÙKÛ›H™]È™XÛÜ™È\™HYYˆHÛ˜ÙKXKY^H[H[H™XÛÜ™]HHY\İ\™^XÚ]™\È[[˜Ü™[Y[[Ûİ™\˜YÙHÚ]İ]™\X]Y]Y\Z[™Ë‚‹H
Š“Ù™‹Zİ\œÊŠˆ™Y™\ˆŒŒ8 $ÌNŒU›Üˆ[Hİ\İZ[™Y˜XÚÙš[ÛÜšÈ
Z[š[Z^™\È[\XİÛˆX›XÈ\Ù\œÈ
ÈÛ\šÈİY™ˆÛˆ]™HŞ\İ[JK‚‹H
Š’\™]›ÚY
ŠˆÈ›İØÜ˜\H[XYÙ\È[Ëˆ]\È›İ
JHHYXÙHHÛ\šÈÙ[ÈHİXœØÜš\[Ûˆ›Ü‹[™
ŠHHYXÙH[ÜİZÙ[HÈ˜]È[ˆX\ÙHÛÛ\Z[‚‚‹KKB‚ˆÈÈ‹ˆØ[\H™\]Y\İÕS•TÕQB‚ŠŠ”XÙZÛ\ˆ8 %Ø[››İ™H™\šYšYYÚ]İ]Hœ›İÜÙ\ˆØ\\™KŠŠˆ™\İYİY\ÜÈ›ÜˆH˜[YHÙX\˜ÚÛİ™\š[™È[ŒH™XÛÜ™È›ÜˆHÚ]™[ˆÜ˜[Ü‚‚˜”ÔÕĞXØÛZ[UÙX‹ÜÙX\˜ÚÔÙX\˜Ú\S˜[YHÌKŒB’Üİˆ˜XÛ]ÙXŒK˜œ™]˜\™Û\šË\ÂÛÛ[U\Nˆ\XØ][Û‹Ş]İİËY›Ü›K]\›[˜ÛÙYÈÚ\œÙ]UU‹NÛÛÚÚYNˆTÔ“‘UÔÙ\ÜÚ[Û’YOÙ\ÜÚ[ÛÈ×Ô™\]Y\İ™\šYšXØ][Û•ÚÙ[OÛÛÚÚYK]ÚÙ[È\ØÛZ[Y\XØÙ\YLB—×Ô™\]Y\İ™\šYšXØ][Û•ÚÙ[ˆ›Ü›K]ÚÙ[‚–T™\]Y\İYUÚ]ˆS™\]Y\İ”™Y™\™\ˆÎ‹Ëİ˜XÛ]ÙXŒK˜œ™]˜\™Û\šË\ËĞXØÛZ[UÙX‹ÜÙX\˜ÚÔÙX\˜Ú\S˜[YB‚“\İ˜[YOTÒTTI‘š\œİ˜[YOPT’QS	”ÙX\˜Ú\™Xİ[ÛX›İ	”™XÛÜ™]Qœ›ÛOLIL‘ŒIL‘ŒŒI”™XÛÜ™]UÏLL‰L‘ŒÌIL‘ŒŒI‘ØÕ\\Ó\İI”YÙTÚ^™OML	”YÙS[X™\LB˜‚ŠŠ[šY[˜[Y\È\™HS‘‘T”‘QŠŠˆ™^\\ÜÈ™XÛÛˆ]\İ™\XÙH\ÈÚ]H™X[Ø\\™Y™\]Y\İ‚‚‹KKB‚ˆÈÈËˆØ[\H™\ÜÛœÙH^Ù\œÕS•TÕQB‚ŠŠ”XÙZÛ\‹ŠŠˆ^XİYÚ\HYˆ”ÓÓ‚‚˜œÛÛ‚Âˆİ[›İÜÈˆKˆœYÙS[X™\ˆˆKˆœYÙTÚ^™HˆLˆœ™\İ[ÈˆÂˆÂˆœ™XÛÜ™]HˆŒŒKLËLM‹ˆ™ØÕ\Hˆ“UÈ‹ˆ˜›ÛÚÈˆNˆ‹ˆœYÙHˆŒLMÈ‹ˆ˜Ù›ˆˆŒŒLÌMLŒÍH‹ˆ™Ü˜[Üˆˆ”ÒTTHT’QS‹ˆ™Ü˜[YHˆ’”SÔ‘ĞSˆÒTÑHS’ÈH‹ˆ˜ÛÛœÚY\˜][ÛˆˆLŒˆ›YØ[\ØÈˆ“ÕÈ“ÈÈSÔ‘TÕÕPˆˆŒÈÈH‹ˆ™]Z[\›ˆ‹ĞXØÛZ[UÙX‹ÑØİ[Y[Ñ]Z[ØÙ›LŒLÌMLŒÍH‹ˆš[XYÙU\›ˆ‹ĞXØÛZ[UÙX‹ÑØİ[Y[Ò[XYÙOØÙ›LŒLÌMLŒÍH‚ˆBˆBŸB˜‚“ÜˆYˆÙ\™\‹\™[™\™YSHX›HÛ\ÜÏHœ™\İ[ËYÜšY˜Ú]X]Ú[™ÈÛÛ[[œË‚‚‹KKB‚ˆÈÈˆÜ[ˆ]Y\İ[ÛœÂ‚ŠŠ’YÚš[Üš]H
›ØÚÙ\œÈ›ÜˆŒˆY\\ŠNŠŠ‚‚ŒKˆ
Š‘^XİÔÕT“
Šˆ›ÜˆXXÚÙX\˜Ú\Jˆ›Ü›H8 %Ù\ÈH›Ü›HÔÕ˜XÚÈÈ]Ù[‹ÜˆÈHÚX›[™ÈÔÙX\˜ÚÑ^Xİ]XÈØ\KÜÙX\˜Ú[™Ú[È™\]Z\™\Èœ›İÜÙ\ˆ]ÛÛÈØ\\™K‚Œ‹ˆ
Š‘^XİšY[˜[Y\È
ÈÙ\šX[^˜][ÛŠŠˆ8 %›Ü›KY[˜ÛÙYœÈ”ÓÓÈØ[Y[Ø\ÙHœÈ\ØØ[Ø\ÙHœÈÛ˜ZÙWØØ\ÙNÈ\İØ\œ˜^H›İ][Û‹‚ŒËˆ
Š[Y›Ü™Ù\HÚÙ[ˆ›İÊŠˆ8 %\ÈH\ØÛZ[Y\‹XXØÙ\ÔÕ™\]Z\™YÛ˜ÙH\ˆÙ\ÜÚ[Û‹Üˆ\È][X™YY\ÈHY[ˆšY[[ˆ]™\HÙX\˜Ú›Ü›OÂˆ
Š”Ù\ÜÚ[ÛˆÛÛÚÚYHY™][YJŠˆ8 %İÈÛ™ÈÙ\ÈH\ØÛZ[Y\‹XXØÙ\YÙ\ÜÚ[Ûˆ™[XZ[ˆ˜[YÈ\‹Xœ›İÜÙ\‹]X‹\‹RTš^YÂKˆ
Š”YÚ[˜][ÛˆYXÚ[šXÜÊŠˆ8 %İ[XÛİ[XY\È”ÓÓˆ[™[ÜOÈSYÙ\ˆ[šÜÏÈX^YÙHÚ^™HØ\Â‹ˆ
Š”™\ÜÛœÙHRSQJŠˆ8 %”ÓÓ‹S\X[ÜˆSÈ[œÜXİÛÛ[U\XÛˆHˆ™\ÜÛœÙK‚Ëˆ
Š‘Øİ[Y[]Z[[™Ú[
Šˆ8 %Ú]T“]\›ˆ™]\›œÈH\‹YØİ[Y[]Z[
[\Y\Ë[YØ[[™[]YØÈ[šÜÊOÈ\ÈÑ“ˆHØ[›ÛšXØ[Ù^HÜˆ\È]›ÛÚËÔYÙOÂˆ
Š’[XYÙHT“]\›ŠŠˆ8 %X›XÈ™]šY]ÜÈœÈİXœØÜš\[Û‹YØ]Y[™\ÛÛ][ÛÈ\È\™HHÒ[XYÙOØÙ›K‹‹˜]™]\›œÈHØ]\›X\šÙYX›XÈ™]šY]ÏÂ‚ŠŠ“YY][Hš[Üš]H
šXÙK]ËZ]™H›ÜˆŒJNŠŠ‚‚Kˆ
Š‘ØË]\HX\İ\ˆ\İ
Šˆ8 %Ú]\™H[˜[YØÕ\XÛÙ\ÈXØÙ\YHHØÕ\HÙX\˜ÚÈZÙ[H[˜ÛY\ÈQQUËTÑËĞUTÈS‹’‹ËÑT•U]Ëˆ8 %]H]]Üš]]]™H\İÚİ[ÛÛYHœ›ÛHH›Ü›IÜÈ›ÜİÛ‹‚ŒLˆ
Š‘]K\˜[™ÙHX^[][HÜ[ŠŠˆ8 %\ÈH[^YX\ˆ˜[YHÙX\˜Ú[İÙYÜˆ\È\™HHÙ\™\‹\ÚYHØ\]K™ËˆL^\ÏÂŒLKˆ
Š“X^[][H™\İ[\Ù]Ú^™JŠˆ8 %Ú[H\\[H™]\›ˆL›İÜÈ›ÜˆHœ›ØY]Y\KÜˆÙ\È]Ø\]K™ËˆL[™™\]Z\™H™Yš[™[Y[ÂŒL‹ˆ
ŠÛÛ˜İ\œ™[\Ù\ÜÚ[Ûˆ[Z]\ˆT
Šˆ8 %[HÛÙ[Z]Ûˆ\˜[[ÙX\˜Ú\Èœ›ÛHHØ[YHTÂ‚ŠŠ“İÈš[Üš]H
Ü\˜][Û˜[
NŠŠ‚‚ŒLËˆ
Š•\›\ÈÙˆ\ÙJŠˆ8 %›Ü›X[İ][Y[Ûˆ›ÙÜ˜[[X]XÈXØÙ\ÜÈ
H\ØÛZ[Y\ˆÛİ™\œÈXØİ\˜XŞK›İXØÙ\ÜÈY]Ù
Kˆ™K\›ÙXİ[ÛˆÙ]YØ[Û\š]HšXHXØÛZ[]\Ù\˜YZ[œ™]˜\™Û\šË\Ø‚ŒMˆ
Š[ËY]HYÜ™Y[Y[™X\ÚXš[]JŠˆ8 %Ù\ÈHÛ\šÈÙ™™\ˆH[ÈXÙ[œÙHÈZ[H[H™YY›ÜˆÛÛ[Y\˜ÚX[\Ù\œÈ
ZÙHšYYYRHÈ]™\™\İ
OÈÛÛXİXØÛZ[]\Ù\˜YZ[œ™]˜\™Û\šË\ØÜˆÙ™šXÚX[™XÛÜ™Ò[XYÙT™\]Y\İĞœ™]˜\™Û\šË\Ø‚ŒMKˆ
ŠXØÛZ[H™[™Ü‹[]™[X›XÈTJŠˆ8 %\œš\È™XÛÜ™[™ÈÛÛ][ÛœÈX^H]™HH\™\‹[]™[TH]Ü˜\ÈXØÛZ[UÙXÈYˆÛËXÙ[œÚ[™È\›\È
È\‹XÛİ[HÜZ[ˆİ]\È\™HÛÜÚXÚÚ[™ÈÚ]”ËTØ[\Ğ\œš\ØÛÛ\]\‹˜ÛÛH
KN‹LÎMÍJK‚‚‹KKB‚ˆÈÈ™^\\ÜÈ™XÛÛˆ[‚‚ŒKˆ
Šœ›İÜÙ\ˆØ\\™H\ÜÊŠˆ8 %Ü[ˆÚ›ÛYH]ÛÛÈ™]ÛÜšÈX‹[ˆH˜[YHÙX\˜Ú
ÈHØÕ\HÙX\˜Ú
ÈH™XÛÜ™]HÙX\˜Ú^ÜT‹^˜XİÔÕT“
ÈXY\œÈ
È^[ØY
È™\ÜÛœÙHØÚ[XKˆ\È[[Z[˜]\È]™\HÕS•TÕQXX›İ™H[ˆÛ™HÚ][™Ë‚Œ‹ˆ
Š‘š\™XÜ˜]ÛÈ^]ÜšYÚ\ÜÊŠˆ8 %ØÜš\Hœ›İÜÙ\‹XØ\\™HÛÜšÈÛÈ]Ø[ˆ™H™K\[ˆ\ˆÚX›[™ÈÛİ[H
ZX[ZKQYKœ›İØ\™[H™XXÚ[Ø›Ü›İYÚ
H][ÛÈ\Ş\ÈXØÛZ[UÙXˆÜˆH™[]Y\]YHÛÛ][ÛœÈÛÙX˜\ÙKˆÛ™H™XÛÛ‹ˆÛİ[Y\Ë‚ŒËˆ
ŠÛÛ[Y\˜ÚX[\]›Ø™JŠˆ8 %[XZ[XØÛZ[]\Ù\˜YZ[œ™]˜\™Û\šË\Ø\ÚÚ[™ÈÚ]\ˆH]K\Ú\š[™ÈYÜ™Y[Y[\È]˜Z[X›H›Üˆ[™^Y“Ñ]H
›İ[XYÙ\ÊNÈYˆY\Ë\ÈXZÙ\ÈHØÜ˜\\ˆØœÛÛ]K‚ˆ
ŠZ[ŒHY\\ŠŠˆ™Z[™H™X]\™H›YË[›š[™ÈÙ[H
H™\HÈÈË˜XÚÙš[HZ[H[HÛ›JKYØZ[œİH™XÛÜ™]HÙX\˜ÚÚ]Hš^YY\İ\™^KY]H8 %İÙ\İİ\™˜XÙKX\™XH]][]™\œÈ™X[˜[YHÚ[H™\ÜXİ[™È]\]Y]K‚‚‹KKB‚ˆÈÈÛÛXİİ\™˜XÙHÕ‘T’Q’QQB‚‹H
Š•XÚšXØ[Èİ\Ü
Šˆ[\ÚĞœ™]˜\™Û\šË\Ø‹H
Š“Ù™šXÚX[™XÛÜ™ÈYZ[ŠŠˆXØÛZ[]\Ù\˜YZ[œ™]˜\™Û\šË\Ø‹H
Š’[XYÙH™\]Y\İÊŠˆÙ™šXÚX[™XÛÜ™Ò[XYÙT™\]Y\İĞœ™]˜\™Û\šË\Ø‹H
Š”Û™JŠˆ
ÌŒJHŒÍËLŒ
Ù™šXÚX[™XÛÜ™È\\Y[
B‹H
Š“XZ[[™ÊŠˆœ™]˜\™Ûİ[HÛ\šÈÙˆÛİ\Ë“Ëˆ›ŞÍË]\İš[K“ÌÎKLÍÂ‹H
Š•™[™Üˆ
XØÛZ[JHØ[\ÊŠˆ”ËTØ[\Ğ\œš\ØÛÛ\]\‹˜ÛÛXKN‹LÎMÍB‚‹KKB‚ŠŠ‘[™ŒKˆ\È\ÈHİ\™˜XÙHX\›İHÜXËŠŠˆHÕS•TÕQXX\šÙ\œÈ\™HÛ™\İ8 %[][™ÈÚ]İ]HÕ‘T’Q’QQXYÈ[ˆ\ÈØÈ\È[™™\™[˜ÙH]™YYÈHœ›İÜÙ\‹XØ\\™H\ÜÈÈÛÛ™š\›K‚
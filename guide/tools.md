# 工具總覽

> 由 `python3 pb.py build` 產生。依第一個階段分組；狀態：已整合、已安裝、待試、待查、未採用、避開。

## 1 內容與架構

| 工具 | 狀態 | 費用 | 授權 | 何時用 |
|---|---|---|---|---|
| [webanalyze（Wappalyzer 開源移植）](https://github.com/rverton/webanalyze)（T-84） | 已整合 | 免費 | MIT（寬鬆） | 想知道參考站用什麼框架、CMS、CDN、分析工具時 |
| [SiteOne Crawler](https://github.com/janreges/siteone-crawler)（T-85） | 已整合 | 免費 | MIT（寬鬆） | 要看參考站或自己網站的頁面結構、SEO、效能、標頭時 |
| [UX 參考站（Laws of UX、NN/g、Apple HIG、Growth.Design）](https://lawsofux.com)（T-76） | 待試 | 免費 | 服務條款（未標） | 設計流程或互動時要找原則與研究依據 |

## 2 設計方向

| 工具 | 狀態 | 費用 | 授權 | 何時用 |
|---|---|---|---|---|
| [designlang（Manavarya09/design-extract）](https://github.com/Manavarya09/design-extract)（T-82） | 已整合 | 免費 | MIT（寬鬆） | 拆解參考站要 token 時（pb.py teardown 會自動跑） |
| [dembrandt](https://github.com/dembrandt/dembrandt)（T-83） | 已整合 | 免費 | MIT（寬鬆） | 要交叉驗證 designlang、或要做設計漂移檢查（--compare）時 |
| [SingleFile CLI](https://github.com/gildas-lormeau/SingleFile)（T-86） | 已整合 | 免費 | AGPL-3.0（只在本機用、不散布，不受影響）（特殊） | 要把參考頁當下的樣子凍結保存（對方改版也不怕）時 |
| [DESIGN.md 規格與 CLI（Google Labs）](https://github.com/google-labs-code/design.md)（T-87） | 已整合 | 免費 | Apache-2.0（寬鬆） | 寫風格合約（DESIGN.md）並檢查時 |
| better-design MCP（T-04） | 已安裝 | 不明 | 不明（未標） | 建設計系統、找圖示庫、審查版面和間距時 |
| [Design DNA（zanwei）](https://github.com/zanwei/design-dna)（T-09） | 已安裝 | 免費 | MIT（寬鬆） | 有參考介面、想把風格量化成規格時 |
| [REA（Reverse Engineer Anything）](https://github.com/morluto/rea)（T-05） | 待試 | 免費 | MIT（寬鬆） | 想知道別人網站的某個互動或效果怎麼做時 |
| [Awesome DESIGN.md（VoltAgent）](https://github.com/VoltAgent/awesome-design-md)（T-06） | 待試 | 免費 | MIT（寬鬆） | 要定設計系統、想看好的 DESIGN.md 怎麼寫時 |
| [網站設計參考圖庫（Land-book、Supahero、Pricing Pages、Social Proof Examples、Navbar Gallery、OG Image Gallery、Deck Gallery、Httpster、Mobbin）](https://land-book.com/)（T-15） | 待試 | 免費 | 網站內容各自所有（未標） | 找版面參考時。原 T-18 的靈感網站清單已併入這裡 |
| [logo-design-skill（kaankiziltug）](https://github.com/kaankiziltug/logo-design-skill)（T-16） | 待試 | 免費 | MIT（寬鬆） | 要做或改 Logo 時 |
| [Claude Code Skill 設計風格圖鑑（Casper）](https://www.casper.tw/claude-skill-design-gallery/)（T-27） | 待試 | 免費 | 未標（repo 無 LICENSE，頁面寫可自由下載修改）（未標） | 挑風格或動效方向時先看成品；寫風格規格時拿它的 SKILL.md 當範本 |
| [ui-ux-pro-max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)（T-37） | 待試 | 免費 | MIT（寬鬆） | 查 UX 規則（--domain ux）與交付前檢查清單時。2026-11-17 實測：--design-system 給的風格方向不貼產業（金融服務給了 Liquid Glass），定方向交給 taste-skill |
| [Recraft](https://www.recraft.ai)（T-52） | 待試 | 部分付費 | 服務條款（特殊） | 發想 logo 方向、想要直接出向量草圖時 |
| [Inkscape](https://inkscape.org)（T-56） | 待試 | 免費 | GPL-2.0+（寬鬆） | 把點陣草圖描成向量、調細節、輸出正式檔時 |
| [Penpot](https://penpot.app)（T-57） | 待試 | 免費 | MPL-2.0（寬鬆） | 排 logo 使用規範、品牌規範頁時 |
| [Coolors](https://coolors.co)（T-58） | 待試 | 部分付費 | 服務條款（未標） | 定品牌配色時 |
| [Godly](https://godly.website)（T-59） | 待試 | 免費 | 服務條款（未標） | 找網頁設計參考時（偏高完成度、動效多的網站） |
| [Awwwards](https://www.awwwards.com)（T-60） | 待試 | 免費 | 服務條款（未標） | 找得獎等級的網頁設計參考時 |
| [WhatFont](https://chromewebstore.google.com/search/whatfont)（T-61） | 待試 | 免費 | 服務條款（未標） | 看到別人網站的字想知道是什麼字時 |
| [Fontshare](https://www.fontshare.com)（T-62） | 待試 | 免費 | ITF Free Font License（寬鬆） | 要找免費可商用的英文字型時 |
| [Fontpair](https://www.fontpair.co)（T-63） | 待試 | 免費 | 服務條款（未標） | 要決定標題字與內文字怎麼搭時 |
| [Realtime Colors](https://www.realtimecolors.com)（T-64） | 待試 | 免費 | 服務條款（未標） | 定配色時，想直接看顏色套在真實網頁上的效果 |
| [Huemint](https://huemint.com)（T-65） | 待試 | 免費 | 服務條款（未標） | 要用 AI 產生配色並看在品牌或網頁上的效果時 |
| [Color Hunt](https://colorhunt.co)（T-66） | 待試 | 免費 | 服務條款（未標） | 想找現成的四色配色靈感時 |
| [fontpls](https://github.com/Jon-Becker/fontpls)（T-88） | 待試 | 免費 | MIT（寬鬆） | 要知道參考站用了哪些字體檔與 @font-face 設定時（只研究，不帶走字體） |
| [design-mobile-apps（Sleek）](https://github.com/designed-by-ai/skills)（T-50） | 待查 | 不明 | MIT（技能）（特殊） | 要快速出手機 App 畫面草稿時；技能本身 MIT，但實際呼叫付費服務 Sleek，要帳號和 API 金鑰 |
| [Shopify Hatchful](https://www.shopify.com/tools/logo-maker)（T-53） | 待查 | 不明 | 服務條款（未標） | 需要快速、免費的套版 logo 時 |
| [Namecheap Logo Maker](https://www.namecheap.com/logo-maker/)（T-54） | 待查 | 不明 | 服務條款（未標） | 需要快速、免費的套版 logo 時 |
| [Design.com](https://www.design.com)（T-55） | 待查 | 不明 | 服務條款（未標） | 需要快速、免費的套版 logo 時 |
| [Figma 官方技能（figma-use、figma-generate-design）](https://github.com/figma/mcp-server-guide)（T-73） | 待查 | 部分付費 | 服務條款（未標） | 設計稿在 Figma 時：讓 agent 讀懂既有元件與變數，或用既有設計系統生成新畫面 |
| [edenspiekermann Skills（audit-design-system、apply-design-system）](https://github.com/edenspiekermann/Skills)（T-74） | 待查 | 不明 | 未查（未標） | 設計稿在 Figma 時，檢查畫面偏離設計系統的地方並改回來 |
| [設計靈感網站（scrolltide、navbar.gallery、footer.design、cta.gallery、minimal.gallery、60fps.design、collectui、landdding、Savee、Cosmos、Design Spells）](https://scrolltide.co/)（T-18） | 未採用 | 免費 | 網站內容各自所有（未標） | 找特定元件或細節的參考時。已併入 T-15 |
| [figmaformotion](https://figmaformotion.com/v2)（T-21） | 未採用 | 付費 | 付費授權（未標） | — |

## 3 視覺設計

| 工具 | 狀態 | 費用 | 授權 | 何時用 |
|---|---|---|---|---|
| [Three.js](https://github.com/mrdoob/three.js)（T-10） | 已整合 | 免費 | MIT（寬鬆） | 頁面真的需要 3D 時 |
| [GSAP](https://github.com/greensock/GSAP)（T-11） | 已整合 | 免費 | GSAP Standard No Charge License（不是開源授權）（特殊） | 網頁動效需要時間軸、捲動觸發、文字拆分時 |
| [Impeccable](https://github.com/pbakaus/impeccable)（T-34） | 已整合 | 免費 | Apache-2.0（寬鬆） | 上線前或改版後自動掃 AI 感與品質問題（npx impeccable detect <網址或資料夾>，62 條規則、不用 API 金鑰）；也有一組設計指令（polish、critique、audit） |
| [pixelfx（patch-gg）](https://github.com/patch-gg/pixelfx)（T-80） | 已整合 | 免費 | MIT（寬鬆） | 頁面或影片要像素風、遊戲感的特效（火焰、爆炸、魔法、拾取、UI 閃光）時。非像素風的品牌不要用 |
| [Taste Skill（design-taste-frontend）](https://github.com/Leonxlnx/taste-skill)（T-12） | 已安裝 | 免費 | MIT（寬鬆） | 要避免 AI 味的版面和視覺時 |
| [unslop](https://github.com/heydamir/unslop)（T-29） | 已安裝 | 免費 | CC BY 4.0（須標註作者）（寬鬆） | 畫面一看就是 AI 做的、要改版或上線前審查視覺時 |
| [GSAP AI Skills（官方）](https://github.com/greensock/gsap-skills)（T-30） | 已安裝 | 免費 | MIT（GSAP 本身含全部外掛免費）（寬鬆） | 用 GSAP 做時間軸、捲動觸發、文字拆分、SVG 變形等網頁動效時 |
| [emilkowalski/skills（emil-design-eng 等）](https://github.com/emilkowalski/skills)（T-36） | 已安裝 | 免費 | MIT（寬鬆） | 做或檢查網頁動畫時 |
| [WebGL 特效（ShaderGradient、Liquid Logo、Liquid Glass JS、React Three Fiber）](https://cindyzhu.com.au/guides/4-github-design-repos)（T-20） | 待試 | 免費 | R3F、Liquid Glass JS 為 MIT；ShaderGradient 未標；Liquid Logo 自訂（特殊） | 首屏需要一個動態重點時 |
| [Hallmark](https://github.com/Nutlope/hallmark)（T-22） | 待試 | 免費 | MIT（圖庫照片各有 CC0／公有領域／CC BY／CC BY-SA，使用時要標註）（寬鬆） | 建新頁、改版既有頁、或只想檢查 AI 感時 |
| [PulsoIcon](https://github.com/CityPulso/PulsoIcon)（T-26） | 待試 | 免費 | ISC（部分圖示沿用 Lucide、Tabler 等原授權；品牌 logo 是各品牌商標）（寬鬆） | 按鈕、連結、分頁要有輕微的滑過動態圖示時 |
| [Motion（原 Framer Motion）](https://motion.dev)（T-40） | 待試 | 免費 | MIT（寬鬆） | CSS 做不到的動效：拖曳、版面切換、跟著捲動的複雜效果 |
| [動畫元件庫（Motion Primitives、Magic UI、Uiverse）](https://motion-primitives.com)（T-41） | 待試 | 免費 | MIT（寬鬆） | 想找現成的動畫元件或小互動（按鈕、載入、切換）時 |
| [Anime.js](https://animejs.com)（T-42） | 待試 | 免費 | MIT（寬鬆） | 不用 React、要輕量的時間軸動畫時 |
| [Anatomy（wheresryan22）](https://github.com/wheresryan22/anatomy)（T-51） | 待試 | 免費 | MIT（寬鬆） | 要解釋「一個東西怎麼運作」（產品結構、流程裡的機關、系統元件）時，畫成可互動的立體剖面圖 |
| [Material Symbols](https://fonts.google.com/icons)（T-68） | 待試 | 免費 | Apache-2.0（寬鬆） | 需要一套大量、可調粗細與填色的圖示時 |
| [Storyset](https://storyset.com)（T-69） | 待試 | 部分付費 | Freepik 授權（特殊） | 需要可改色、可做動畫的情境插畫時 |
| [Humaaans](https://www.humaaans.com)（T-70） | 待試 | 免費 | 服務條款（未標） | 需要可自由組合的人物插畫時 |
| [Unsplash](https://unsplash.com)（T-71） | 待試 | 免費 | Unsplash License（寬鬆） | 需要免費高品質照片時 |
| [Lummi](https://www.lummi.ai)（T-72） | 待試 | 部分付費 | 服務條款（未標） | 需要 AI 生成風格的免費圖庫照片時 |
| [MotionSites claude-skill](https://github.com/Motionsites-AI/claude-skill)（T-81） | 待試 | 部分付費 | 技能 MIT；範例與素材 © MotionSites：可用來做網站（含客戶案），不可轉售或打包再散布（特殊） | 要快速做一頁高動態感的登陸頁草稿（影片背景、3D、捲動動畫）時；正式品牌站仍以設計系統為準 |
| [animation-reverse-engineering（技能）](https://github.com/scriptscrypt/animation-reverse-engineering)（T-89） | 待試 | 免費 | README 寫 MIT（repo 沒有授權檔）（未標） | 參考站的動畫是 JS、canvas 或 WebGL 驅動，getAnimations 讀不到時 |
| [Originkit](https://www.originkit.dev/)（T-32） | 待查 | 免費 | 未標（MCP repo 是 MIT，元件本身授權未寫）（未標） | 找現成的網頁動畫元件時 |
| [AI Particle Simulator（casberry）](https://particles.casberry.in/)（T-33） | 待查 | 不明 | 未標（未標） | 要做粒子背景或片頭粒子效果時 |
| [Spline](https://spline.design)（T-45） | 待查 | 部分付費 | 商業服務（特殊） | 想在網頁放可互動的 3D 場景時 |
| [Motion Design 技能（LottieFiles）](https://github.com/LottieFiles/motion-design-skill)（T-14） | 未採用 | 免費 | MIT（寬鬆） | 要設計動效的時間、緩動、編排時。影片手冊 P1 比較由 emil 與 GSAP 技能勝出 |
| [ScrollCraft](https://github.com/singhharsh1708/scrollcraft)（T-17） | 未採用 | 免費 | MIT（寬鬆） | 要做捲動驅動的網站時 |
| [插圖與 3D 圖示（Open Peeps、3dicons、unDraw）](https://www.openpeeps.com)（T-44） | 未採用 | 免費 | CC0（Open Peeps、3dicons）、unDraw 自有授權（特殊） | 照片表達不了、需要插圖或 3D 圖示時 |

## 4 建置

| 工具 | 狀態 | 費用 | 授權 | 何時用 |
|---|---|---|---|---|
| [Modern Web Guidance](https://github.com/GoogleChrome/modern-web-guidance)（T-48） | 已安裝 | 免費 | Apache-2.0（寬鬆） | 寫元件、表單、動效或想把舊寫法換成瀏覽器內建功能時。寫介面前用 `npx modern-web-guidance search "<需求>"` 查標準做法（負責人允許後實跑：回傳 10 個相關做法，含無障礙與退路） |
| [網頁動態元件庫（React Bits、Aceternity UI）](https://reactbits.dev/)（T-19） | 待試 | 部分付費 | 依各庫條款（特殊） | 要動態文字、背景、區塊時 |
| [daisyUI](https://daisyui.com/)（T-31） | 待試 | 免費 | MIT（寬鬆） | 用 Tailwind 做元件，想要語意化的元件類別和主題時 |
| [Component Gallery](https://component.gallery)（T-38） | 待試 | 免費 | 網站內容各自所有（特殊） | 不確定一個元件叫什麼、該怎麼表現時 |
| [21st.dev](https://21st.dev)（T-39） | 待試 | 部分付費 | 各元件不同（特殊） | 想借現成的 React 區塊（價格表、FAQ、主視覺）時 |
| [shadcn/ui](https://ui.shadcn.com)（T-43） | 待試 | 免費 | MIT（寬鬆） | 需要一套可完全擁有、可改的基礎元件時。React 專案預設用它（其他元件庫多半以它為基礎） |
| Image to Code（T-08） | 未採用 | 不明 | 未標（未標） | — |
| [mapcn](https://github.com/AnmolSaini16/mapcn)（T-46） | 未採用 | 免費 | MIT（寬鬆） | 頁面需要地圖（標記、路線）時 |

## 5 品質

| 工具 | 狀態 | 費用 | 授權 | 何時用 |
|---|---|---|---|---|
| [Web Design Guidelines（Vercel）](https://github.com/vercel-labs/agent-skills)（T-13） | 已安裝 | 免費 | 未標（未標） | 審查介面是否符合規範時 |
| [Playwright CLI（Microsoft）](https://github.com/microsoft/playwright-cli)（T-07） | 待試 | 免費 | Apache-2.0（寬鬆） | 要批次截圖、查選擇器、錄測試時（Puppeteer 是同類工具，不另收） |
| [agency-agents（網站挑 3 個）](https://github.com/msitarzewski/agency-agents)（T-28） | 待試 | 免費 | MIT（寬鬆） | 上線前要獨立審查：通用感、無障礙、受眾模擬 |
| [agent-browser（Vercel Labs）](https://github.com/vercel-labs/agent-browser)（T-49） | 待試 | 免費 | Apache-2.0（寬鬆） | 要讓 agent 實際開頁面、填表單、多寬度截圖檢查時；和 Playwright CLI（T-07）比 |
| [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)（T-67） | 待試 | 免費 | 服務條款（未標） | 檢查文字與背景的對比是否達 WCAG AA／AAA 時 |
| [axe-core（Deque）](https://github.com/dequelabs/axe-core)（T-79） | 待試 | 免費 | MPL-2.0（寬鬆） | 上線前自動檢查無障礙問題時（可接 Playwright 每次跑） |
| [uSpec（create-voice）](https://github.com/redongreen/uSpec)（T-75） | 待查 | 不明 | 未查（未標） | 交接前要寫螢幕閱讀器規格時 |

## 6 SEO 與 AI 搜尋

| 工具 | 狀態 | 費用 | 授權 | 何時用 |
|---|---|---|---|---|
| [GEO Optimizer](https://github.com/Auriti-Labs/geo-optimizer-skill)（T-03） | 待試 | 不明 | MIT（寬鬆） | 檢查網站對 ChatGPT、Perplexity、Google AI 摘要、Gemini、Claude 的能見度，給 0–100 分、九大類結果和修正建議 |
| [Claude SEO](https://github.com/AgriciDaniel/claude-seo)（T-23） | 待試 | 免費 | MIT（寬鬆） | 網站上線前後做 SEO 與 AI 搜尋健檢 |
| [geo-seo-claude](https://github.com/zubair-trabzada/geo-seo-claude)（T-35） | 待試 | 免費 | MIT（寬鬆） | 做 AI 搜尋能見度健檢時 |
| [localseoskills](https://github.com/garrettjsmith/localseoskills)（T-24） | 未採用 | 部分付費 | MIT（寬鬆） | 做在地商家的 SEO：Google 商家檔案、評論、名錄、在地關鍵字、AI 在地搜尋。W5 比較：保留 T-35 geo-seo-claude（主用）與 T-23 Claude SEO（範圍廣） |
| [All-In-One Free SEO Tool](https://github.com/IamRamgarhia/All-In-One-Free-SEO-Tool)（T-25） | 未採用 | 免費 | MIT（寬鬆） | 要免費做關鍵字研究、關鍵字缺口、競品比較、AI 能見度、在地 SEO 時。W5 比較：保留 T-35 geo-seo-claude（主用）與 T-23 Claude SEO（範圍廣） |
| [NotFair Plugin（原 TopRank）](https://github.com/nowork-studio/notfair-plugin)（T-47） | 未採用 | 免費 | MIT（寬鬆） | 做 SEO、GEO 健檢與內容時。W5 比較：保留 T-35 geo-seo-claude（主用）與 T-23 Claude SEO（範圍廣） |
| [OpenSEO](https://github.com/every-app/open-seo)（T-02） | 避開 | 付費 | MIT（寬鬆） | 開源版的 Semrush／Ahrefs：關鍵字研究、排名追蹤、反向連結、網站健檢 |

## 7 上線

| 工具 | 狀態 | 費用 | 授權 | 何時用 |
|---|---|---|---|---|
| [Vercel](https://vercel.com)（T-77） | 待試 | 部分付費 | 服務條款（未標） | 部署 Next.js 等前端並產生預覽網址時。商業網站不能用免費 Hobby 方案（見陷阱條目） |
| [Sentry](https://sentry.io)（T-78） | 待試 | 部分付費 | FSL（程式碼）／服務條款（特殊） | 網站上線後要知道使用者遇到什麼錯誤時 |

## 8 量測與迭代

| 工具 | 狀態 | 費用 | 授權 | 何時用 |
|---|---|---|---|---|
| [Google Search Console MCP（Suganthan）](https://github.com/Suganthan-Mohanadasan/Suganthans-GSC-MCP)（T-01） | 待試 | 免費 | Apache-2.0（寬鬆） | 讓 Claude 直接讀 Search Console 的搜尋數據：找出排名在第 2 頁、差一點就上首頁的關鍵字，建議要改哪一頁；29 個工具，每次回答附資料出處 |

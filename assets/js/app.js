/**
 * Tamil Nadu Politics Brief - Pure-English Newspaper UI Engine
 * - Preserves newline breaks (\n) so bullet points never collapse into a wall of text
 * - Strips any legacy '&nbsp;' or robotic boilerplate sentences on render
 * - Displays fixed 6:00 AM / 6:00 PM IST coverage windows across all pages including Archive
 */

const TN_PARTIES = [
    "DMK", "AIADMK", "BJP", "INC", "TVK", "PMK",
    "NTK", "VCK", "MDMK", "DMDK", "AMMK", "Left Parties"
];

const TN_TOPICS = [
    "Government & Administration",
    "Political Parties",
    "Assembly, Courts & Policy",
    "Elections",
    "Education & NEET",
    "Agriculture & Water",
    "Public Protests & Labour",
    "Centre–State Relations",
    "Infrastructure & Economy"
];

const TN_DISTRICTS = [
    "Ariyalur", "Chengalpattu", "Chennai", "Coimbatore", "Cuddalore", "Dharmapuri",
    "Dindigul", "Erode", "Kallakurichi", "Kancheepuram", "Kanniyakumari", "Karur",
    "Krishnagiri", "Madurai", "Mayiladuthurai", "Nagapattinam", "Namakkal", "Nilgiris",
    "Perambalur", "Pudukkottai", "Ramanathapuram", "Ranipet", "Salem", "Sivaganga",
    "Tenkasi", "Thanjavur", "Theni", "Thoothukudi", "Tiruchirappalli", "Tirunelveli",
    "Tirupathur", "Tiruppur", "Tiruvallur", "Tiruvannamalai", "Tiruvarur", "Vellore",
    "Viluppuram", "Virudhunagar"
];

const PLACEHOLDER_PHRASES = [
    "refer to the top developments",
    "judicial and legislative developments from this window are listed",
    "no disputed partisan claims flagged",
    "no disputed political claims flagged",
    "next automated edition publishes at the next",
    "next automated edition runs in",
    "configure gemini_api_key",
    "see source links below for primary reports",
    "regional reporting in this window covered:"
];

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

/**
 * Cleans text while PRESERVING newline breaks (\n) so bullet lists work properly!
 * Also strips any legacy '&nbsp;' bundles or robotic filler sentences from older JSON files.
 */
function ensurePureEnglish(str) {
    if (!str) return "";
    return String(str)
        .replace(/\r\n/g, "\n")
        .split("\n")
        .map(line => {
            let l = line
                .replace(/&nbsp;.*$/gi, "")
                .replace(/&#x[0-9a-f]+;?/gi, "")
                .replace(/The development directly involves [^.]+\./gi, "")
                .replace(/The matter is being addressed by state administrative authorities [^.]+\./gi, "")
                .replace(/Reporting from [^.]+\./gi, "")
                .replace(/^(?:JUST\s+NOW|BREAKING\s+NEWS|\d+\s*-\s*)/i, "")
                .replace(/[\u0B80-\u0BFF]+/g, " ")
                .replace(/\s*\|\s*/g, " ")
                .replace(/[ \t]{2,}/g, " ")
                .trim();
            return l;
        })
        .filter(Boolean)
        .join("\n");
}

function isMeaningfulContent(val) {
    if (!val) return false;
    if (Array.isArray(val)) return val.length > 0;
    const text = ensurePureEnglish(val);
    if (!text || text.length < 20) return false;
    const lower = text.toLowerCase();
    return !PLACEHOLDER_PHRASES.some(p => lower.includes(p));
}

function formatReadableIST(isoStr) {
    if (!isoStr) return "";
    const dt = new Date(isoStr);
    if (isNaN(dt.getTime())) return escapeHtml(isoStr);
    return dt.toLocaleString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
        timeZone: "Asia/Kolkata"
    }) + " IST";
}

/**
 * Always displays the official fixed 12-hour Coverage Window for an edition
 * (6:00 PM prev day - 6:00 AM for Morning; 6:00 AM - 6:00 PM for Evening)
 */
function getFixedCoverageWindowText(dateStr, editionType) {
    if (!dateStr) return "";
    const [y, m, d] = dateStr.split("-").map(Number);
    if (!y || !m || !d) return escapeHtml(dateStr);
    if (editionType === "morning") {
        const endDt = new Date(Date.UTC(y, m - 1, d, 0, 30, 0)); // 6:00 AM IST
        const startDt = new Date(endDt.getTime() - 12 * 3600 * 1000); // 6:00 PM prev day IST
        return `${formatReadableIST(startDt.toISOString())} – ${formatReadableIST(endDt.toISOString())}`;
    } else {
        const startDt = new Date(Date.UTC(y, m - 1, d, 0, 30, 0)); // 6:00 AM IST
        const endDt = new Date(Date.UTC(y, m - 1, d, 12, 30, 0)); // 6:00 PM IST
        return `${formatReadableIST(startDt.toISOString())} – ${formatReadableIST(endDt.toISOString())}`;
    }
}

function formatStatusLabel(status) {
    const map = {
        "published": "Verified Edition",
        "published_delayed": "Published Edition",
        "published_quiet_window": "Quiet Window",
        "published_extractive_fallback": "Verified Edition"
    };
    return map[status] || "Published Edition";
}

function formatInlineMarkdown(escapedStr) {
    return escapedStr
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}

function formatEditorialText(str, forceBullets = false) {
    if (!str) return "";
    let cleaned = ensurePureEnglish(str);

    // Split any inline " - **Headline:**" or ". - Title:" that got merged into a single line
    cleaned = cleaned
        .replace(/\.\s+-\s+(?=[A-Z*])/g, ".\n- ")
        .replace(/\s+-\s+\*\*/g, "\n- **");

    const lines = cleaned.split("\n").map(l => l.trim()).filter(Boolean);
    if (!lines.length) return "";

    const isBulletList = forceBullets || lines.some(l => /^[-*•]\s+/.test(l));
    if (isBulletList) {
        const items = lines
            .map(l => {
                const stripped = l.replace(/^[-*•]\s+/, "").trim();
                return `<li style="margin-bottom:0.75rem;line-height:1.65;">${formatInlineMarkdown(escapeHtml(stripped))}</li>`;
            })
            .join("");
        return `<ul style="padding-left:1.35rem;margin-bottom:0.85rem;">${items}</ul>`;
    }

    return lines
        .map(l => `<p style="margin-bottom:0.85rem;">${formatInlineMarkdown(escapeHtml(l))}</p>`)
        .join("");
}

function shareOnWhatsApp(editionId, headline) {
    const baseUrl = window.location.origin + window.location.pathname.replace(/[^/]*$/, "");
    const fullUrl = `${baseUrl}edition.html?id=${encodeURIComponent(editionId)}`;
    const text = `${ensurePureEnglish(headline)} — Tamil Nadu Politics Brief: ${fullUrl}`;
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, "_blank", "noopener");
}

function copyEditionLink(editionId) {
    const baseUrl = window.location.origin + window.location.pathname.replace(/[^/]*$/, "");
    const fullUrl = `${baseUrl}edition.html?id=${encodeURIComponent(editionId)}`;
    if (navigator.clipboard) {
        navigator.clipboard.writeText(fullUrl);
        alert("Edition link copied to clipboard!");
    }
}

function initTheme() {
    const saved = localStorage.getItem("tnpb_theme") || "dark";
    document.documentElement.setAttribute("data-theme", saved);
    const btn = document.getElementById("theme-toggle");
    if (btn) {
        btn.textContent = saved === "dark" ? "Light Mode" : "Dark Mode";
        btn.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme");
            const next = current === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            localStorage.setItem("tnpb_theme", next);
            btn.textContent = next === "dark" ? "Light Mode" : "Dark Mode";
        });
    }
    const clockEl = document.getElementById("ist-date-display");
    if (clockEl) {
        clockEl.textContent = new Date().toLocaleDateString("en-IN", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
            timeZone: "Asia/Kolkata"
        }) + " (IST)";
    }
}

function renderEditionCard(ed, slotLabel) {
    if (!ed) {
        return `
      <div class="card">
        <div class="card-kicker">${escapeHtml(slotLabel)}</div>
        <h3>Edition Awaiting Scheduled Run</h3>
        <p class="meta-line">Target schedule: 6:00 AM / 6:00 PM IST.</p>
      </div>
    `;
    }
    const badge = ed.is_test_sample
        ? `<span class="badge badge-warn">SAMPLE TEST DATA</span>`
        : `<span class="badge badge-verified">${escapeHtml(formatStatusLabel(ed.status))}</span>`;

    const partyBadges = (ed.parties || [])
        .slice(0, 6)
        .map(p => `<span class="badge badge-tag">${escapeHtml(p)}</span>`)
        .join("");

    const cleanHeadline = ensurePureEnglish(ed.headline) || "Tamil Nadu Political Briefing";
    const fixedWindow = getFixedCoverageWindowText(ed.date, ed.edition_type);

    return `
    <article class="card">
      <div class="card-kicker">${escapeHtml(slotLabel)} &bull; ${escapeHtml(ed.date)}</div>
      <div style="margin-bottom:0.5rem;">${badge}</div>
      <h2><a href="${escapeHtml(ed.url)}">${escapeHtml(cleanHeadline)}</a></h2>
      <p class="meta-line">
        <strong>Window:</strong> ${fixedWindow}<br>
        <strong>Published:</strong> ${formatReadableIST(ed.published_at_ist)} &bull; ~${escapeHtml(ed.reading_time_minutes)} min read
      </p>
      <div style="margin-bottom:0.85rem;font-size:0.95rem;">
        ${formatEditorialText(ed.big_picture_excerpt || "", true)}
      </div>
      <div style="margin-bottom:0.85rem;">${partyBadges}</div>
      <a href="${escapeHtml(ed.url)}" style="font-family:var(--font-sans);font-weight:600;font-size:0.9rem;">
        Read Full Briefing &rarr;
      </a>
    </article>
  `;
}

function renderFullEditionView(container, ed) {
    const sec = ed.sections || {};

    const validDevs = (sec.top_developments || []).filter(d => {
        const h = ensurePureEnglish(d.headline);
        return h && h.length >= 12 && !/vijaya\s+deepika|vijayawada|uddhav\s+thackeray|kishan\s+reddy/i.test(h);
    });

    const devsHtml = validDevs.map((d, i) => {
        const headlineClean = ensurePureEnglish(d.headline);
        const rawBody = ensurePureEnglish(d.summary || d.what_happened || "");
        const hasDistinctBody = rawBody && rawBody.toLowerCase() !== headlineClean.toLowerCase();

        const seenPubs = new Set();
        const shortSources = [];
        for (const s of (d.sources || [])) {
            const pubName = (s.publisher || "Source")
                .replace(/TN Secretariat & Policy Wire|TN Political Parties Wire|TN Districts Regional Wire|Madras High Court & Assembly Wire/gi, "News Report")
                .replace(/\s*\(.*?\)\s*/g, "")
                .trim();
            if (s.url && !seenPubs.has(pubName)) {
                seenPubs.add(pubName);
                shortSources.push(`<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(pubName)}</a>`);
            }
        }

        const involved = d.who_is_involved && d.who_is_involved !== "State Administration / Public Stakeholders"
            ? `<span class="badge badge-tag">${escapeHtml(d.who_is_involved)}</span>`
            : "";

        // Hide generic computer-generated "This development shapes..." lines
        const whyClean = ensurePureEnglish(d.why_it_matters || "");
        const showWhy = whyClean && !/^this development shapes|^affects |^relates to /i.test(whyClean);
        const whyHtml = showWhy
            ? `<p style="border-left:3px solid var(--accent-blue);padding-left:0.75rem;margin:0.65rem 0;color:var(--text-secondary);font-size:0.95rem;"><strong>Why it matters:</strong> ${escapeHtml(whyClean)}</p>`
            : "";

        return `
      <article class="story-item">
        <div style="margin-bottom:0.45rem;">
          <span class="badge badge-verified">${escapeHtml(d.verification_badge || "Verified Report")}</span>
          ${involved}
        </div>
        <h3 style="margin-bottom:0.6rem;">${i + 1}. ${escapeHtml(headlineClean)}</h3>
        ${hasDistinctBody ? `<div style="margin-bottom:0.65rem;">${formatEditorialText(rawBody)}</div>` : ""}
        ${whyHtml}
        <div class="meta-line" style="margin-bottom:0;padding-top:0.4rem;border-top:1px solid var(--border-color);">
          <strong>Source:</strong> ${shortSources.join(" &bull; ") || "Official Release"}
        </div>
      </article>
    `;
    }).join("");

    // Build concise, clean bulleted Big Picture
    const bigPictureBullets = validDevs.slice(0, 5).map(d => {
        const h = ensurePureEnglish(d.headline).replace(/\.$/, "");
        const s = ensurePureEnglish(d.summary || d.what_happened || "").split(". ")[0].replace(/\.$/, "");
        const bodyPart = s && s.toLowerCase() !== h.toLowerCase() ? ` — ${s}.` : ".";
        return `<li style="margin-bottom:0.7rem;line-height:1.6;"><strong>${escapeHtml(h)}</strong>${escapeHtml(bodyPart)}</li>`;
    }).join("");
    const bigPictureHtml = bigPictureBullets
        ? `<ul style="padding-left:1.35rem;margin-bottom:0.85rem;">${bigPictureBullets}</ul>`
        : formatEditorialText(sec.big_picture, true);

    // Bottom Sources section: ONLY list sources from the top stories shown on the page (max 15)
    const citedSources = [];
    const seenSourceUrls = new Set();
    for (const d of validDevs) {
        for (const s of (d.sources || [])) {
            if (s.url && !seenSourceUrls.has(s.url)) {
                seenSourceUrls.add(s.url);
                citedSources.push(s);
            }
        }
    }

    const sourcesHtml = citedSources.slice(0, 16).map(s => {
        const shortPub = (s.publisher || "Source")
            .replace(/TN Secretariat & Policy Wire|TN Political Parties Wire|TN Districts Regional Wire|Madras High Court & Assembly Wire/gi, "News Report")
            .replace(/\s*\(.*?\)\s*/g, "")
            .trim();
        const cleanTitle = ensurePureEnglish(s.title || shortPub);
        const shortTitle = cleanTitle.length > 72 ? cleanTitle.slice(0, 69) + "..." : cleanTitle;
        return `<li style="margin-bottom:0.45rem;"><strong>${escapeHtml(shortPub)}:</strong> <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(shortTitle)}</a></li>`;
    }).join("");

    const fixedWindow = getFixedCoverageWindowText(ed.date, ed.edition_type);

    const dynamicSections = [
        {
            id: "sec-info",
            toc: "Edition Info",
            title: null,
            html: `
        <div class="card-kicker">${escapeHtml(ed.edition_type.toUpperCase())} EDITION &bull; ${escapeHtml(ed.date)}</div>
        <h1 style="font-size:2rem;line-height:1.25;margin:0.4rem 0 0.75rem;">${escapeHtml(ensurePureEnglish(ed.headline))}</h1>
        <p class="meta-line">
          <strong>Edition:</strong> ${escapeHtml(ed.title)}<br>
          <strong>Coverage Window:</strong> ${fixedWindow}<br>
          <strong>Published:</strong> ${formatReadableIST(ed.published_at_ist)} &bull;
          <strong>Reading Time:</strong> ~${escapeHtml(ed.reading_time_minutes)} min
        </p>
      `,
            show: true
        },
        {
            id: "sec-big-picture",
            toc: "The Big Picture",
            title: "The Big Picture",
            html: bigPictureHtml,
            show: Boolean(bigPictureHtml)
        },
        {
            id: "sec-top-devs",
            toc: "Top Developments",
            title: "Top Political Developments",
            html: devsHtml,
            show: Boolean(devsHtml)
        },
        {
            id: "sec-gov",
            toc: "Government & Admin",
            title: "Government and Administration",
            html: formatEditorialText(sec.government_and_administration, true),
            show: isMeaningfulContent(sec.government_and_administration)
        },
        {
            id: "sec-parties",
            toc: "Political Parties",
            title: "Political Parties and Opposition",
            html: formatEditorialText(sec.political_parties_and_opposition, true),
            show: isMeaningfulContent(sec.political_parties_and_opposition)
        },
        {
            id: "sec-courts",
            toc: "Assembly & Courts",
            title: "Assembly, Courts, and Policy",
            html: formatEditorialText(sec.assembly_courts_and_policy, true),
            show: isMeaningfulContent(sec.assembly_courts_and_policy)
        },
        {
            id: "sec-districts",
            toc: "District Updates",
            title: "District-Level Developments",
            html: formatEditorialText(sec.district_developments, true),
            show: isMeaningfulContent(sec.district_developments)
        },
        {
            id: "sec-sources",
            toc: "Sources",
            title: "Sources and Further Reading",
            html: `<ul style="padding-left:1.2rem;">${sourcesHtml}</ul>`,
            show: Boolean(sourcesHtml)
        }
    ];

    const activeSections = dynamicSections.filter(s => s.show);

    const tocHtml = activeSections
        .map(s => `<li><a href="#${s.id}">${escapeHtml(s.toc)}</a></li>`)
        .join("");

    const bodySectionsHtml = activeSections
        .map(s => `
      <section id="${s.id}" class="section-block">
        ${s.title ? `<h2>${escapeHtml(s.title)}</h2>` : ""}
        ${s.html}
      </section>
    `)
        .join("");

    container.innerHTML = `
    <div class="edition-layout">
      <aside class="toc-sidebar">
        <h4>Edition Contents</h4>
        <ul>${tocHtml}</ul>
        <hr style="margin:0.85rem 0;border:none;border-top:1px solid var(--border-color);">
        <button onclick="shareOnWhatsApp('${escapeHtml(ed.edition_id)}', '${escapeHtml(ensurePureEnglish(ed.headline).replace(/'/g, "\\'"))}')" class="theme-btn" style="width:100%;background:#1f8b4c;color:#fff;border:none;padding:0.5rem;margin-bottom:0.45rem;font-weight:600;">Share on WhatsApp</button>
        <button onclick="copyEditionLink('${escapeHtml(ed.edition_id)}')" class="theme-btn" style="width:100%;padding:0.45rem;margin-bottom:0.45rem;">Copy Edition Link</button>
        <button onclick="window.print()" class="theme-btn" style="width:100%;padding:0.45rem;">Print / Save PDF</button>
      </aside>
      <div class="reading-column">
        ${bodySectionsHtml}
      </div>
    </div>
  `;
}

async function initHomePage() {
    const statusEl = document.getElementById("system-status-banner");
    const cardsEl = document.getElementById("latest-editions-grid");
    const inlineEditionEl = document.getElementById("lead-edition-preview");
    if (!cardsEl) return;

    try {
        const res = await fetch("data/latest-editions.json", { cache: "no-store" });
        const data = await res.json();

        if (statusEl) {
            statusEl.textContent = `Latest edition updated on ${formatReadableIST(data.last_updated_ist)}`;
        }

        cardsEl.innerHTML =
            renderEditionCard(data.morning, "Morning Brief (6:00 AM IST)") +
            renderEditionCard(data.evening, "Evening Brief (6:00 PM IST)");

        let mostRecent = data.evening || data.morning;
        if (data.morning && data.evening) {
            mostRecent = new Date(data.evening.published_at_ist) >= new Date(data.morning.published_at_ist)
                ? data.evening
                : data.morning;
        }

        if (mostRecent && mostRecent.json_path && inlineEditionEl) {
            const edRes = await fetch(mostRecent.json_path, { cache: "no-store" });
            const edFull = await edRes.json();
            renderFullEditionView(inlineEditionEl, edFull);
        }
    } catch (err) {
        cardsEl.innerHTML = `<div class="card"><p>Unable to load latest editions: ${escapeHtml(err.message)}</p></div>`;
    }
}

async function initEditionPage() {
    const container = document.getElementById("full-edition-container");
    if (!container) return;

    const params = new URLSearchParams(window.location.search);
    const editionId = params.get("id");

    try {
        const idxRes = await fetch("data/archive-index.json", { cache: "no-store" });
        const idxData = await idxRes.json();
        const editions = idxData.editions || [];
        const target = editionId
            ? editions.find(e => e.edition_id === editionId)
            : editions[0];

        if (!target) {
            container.innerHTML = `<div class="card"><h2>Edition Not Found</h2></div>`;
            return;
        }

        const edRes = await fetch(target.json_path, { cache: "no-store" });
        const edData = await edRes.json();
        document.title = `${edData.title} | Tamil Nadu Politics Brief`;
        renderFullEditionView(container, edData);
    } catch (err) {
        container.innerHTML = `<div class="card"><p>Error loading edition: ${escapeHtml(err.message)}</p></div>`;
    }
}

function populateSelect(selectEl, items, defaultLabel) {
    if (!selectEl) return;
    selectEl.innerHTML = `<option value="">${escapeHtml(defaultLabel)}</option>` +
        items.map(i => `<option value="${escapeHtml(i)}">${escapeHtml(i)}</option>`).join("");
}

async function initArchivePage() {
    const listEl = document.getElementById("archive-results");
    if (!listEl) return;

    const dateInput = document.getElementById("filter-date");
    const typeSelect = document.getElementById("filter-type");
    const partySelect = document.getElementById("filter-party");
    const topicSelect = document.getElementById("filter-topic");
    const districtSelect = document.getElementById("filter-district");

    populateSelect(partySelect, TN_PARTIES, "All Political Parties");
    populateSelect(topicSelect, TN_TOPICS, "All Topics");
    populateSelect(districtSelect, TN_DISTRICTS, "All 38 Districts");

    const res = await fetch("data/archive-index.json", { cache: "no-store" });
    const data = await res.json();
    const allEditions = data.editions || [];

    function applyFilters() {
        const fDate = dateInput ? dateInput.value : "";
        const fType = typeSelect ? typeSelect.value : "";
        const fParty = partySelect ? partySelect.value : "";
        const fTopic = topicSelect ? topicSelect.value : "";
        const fDistrict = districtSelect ? districtSelect.value : "";

        const filtered = allEditions.filter(ed => {
            if (fDate && ed.date !== fDate) return false;
            if (fType && ed.edition_type !== fType) return false;
            if (fParty && !(ed.parties || []).includes(fParty)) return false;
            if (fTopic && !(ed.topics || []).includes(fTopic)) return false;
            if (fDistrict && !(ed.districts || []).includes(fDistrict)) return false;
            return true;
        });

        if (!filtered.length) {
            listEl.innerHTML = `<div class="card"><p>No archived editions match the selected filters.</p></div>`;
            return;
        }

        listEl.innerHTML = filtered.map(ed => `
      <article class="card" style="margin-bottom:1rem;">
        <div class="card-kicker">${escapeHtml(ed.date)} &bull; ${escapeHtml(ed.edition_type.toUpperCase())} EDITION</div>
        <h3><a href="${escapeHtml(ed.url)}">${escapeHtml(ensurePureEnglish(ed.headline))}</a></h3>
        <p class="meta-line">
          <strong>Coverage Window:</strong> ${getFixedCoverageWindowText(ed.date, ed.edition_type)}<br>
          <strong>Published:</strong> ${formatReadableIST(ed.published_at_ist)} &bull; ~${escapeHtml(ed.reading_time_minutes)} min read
        </p>
        <div>
          ${(ed.parties || []).map(p => `<span class="badge badge-tag">${escapeHtml(p)}</span>`).join("")}
        </div>
      </article>
    `).join("");
    }

    [dateInput, typeSelect, partySelect, topicSelect, districtSelect].forEach(el => {
        if (el) el.addEventListener("input", applyFilters);
    });

    applyFilters();
}

async function initSearchPage() {
    const inputEl = document.getElementById("search-query-input");
    const resultsEl = document.getElementById("search-results-list");
    if (!inputEl || !resultsEl) return;

    const res = await fetch("data/archive-index.json", { cache: "no-store" });
    const data = await res.json();
    const editions = data.editions || [];

    function runSearch() {
        const q = inputEl.value.trim().toLowerCase();
        if (!q) {
            resultsEl.innerHTML = `<p class="meta-line">Enter a keyword above to search all historical briefings.</p>`;
            return;
        }

        const matches = editions.filter(ed => {
            const haystack = [
                ed.title, ed.headline, ed.summary_text,
                ...(ed.parties || []), ...(ed.topics || []), ...(ed.districts || [])
            ].join(" ").toLowerCase();
            return haystack.includes(q);
        });

        if (!matches.length) {
            resultsEl.innerHTML = `<div class="card"><p>No historical editions found matching "<strong>${escapeHtml(q)}</strong>".</p></div>`;
            return;
        }

        resultsEl.innerHTML = matches.map(ed => `
      <article class="card" style="margin-bottom:1rem;">
        <div class="card-kicker">${escapeHtml(ed.date)} &bull; ${escapeHtml(ed.edition_type.toUpperCase())}</div>
        <h3><a href="${escapeHtml(ed.url)}">${escapeHtml(ensurePureEnglish(ed.headline))}</a></h3>
        <p class="meta-line">Coverage Window: ${getFixedCoverageWindowText(ed.date, ed.edition_type)}</p>
        <a href="${escapeHtml(ed.url)}">Open Edition &rarr;</a>
      </article>
    `).join("");
    }

    inputEl.addEventListener("input", runSearch);
    document.querySelectorAll(".quick-chip").forEach(btn => {
        btn.addEventListener("click", () => {
            inputEl.value = btn.getAttribute("data-keyword");
            runSearch();
        });
    });
    runSearch();
}

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initHomePage();
    initEditionPage();
    initArchivePage();
    initSearchPage();
});
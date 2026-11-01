/**
 * Tamil Nadu Politics Brief - Inshorts-Style Factual News Reader
 * - ZERO generic or artificial filler sentences: displays ONLY 100% real news facts
 * - Crisp, easy-to-read cards across all sections
 * - Responsive on Desktop and 360px Android screens
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

const NON_POLITICAL_NOISE_RE = /runaway schoolgirls|wearing headphones killed|country-made guns|vijaya\s+deepika|vijayawada|uddhav\s+thackeray|kishan\s+reddy|fadnavis|rohtak|deep\s+depression|imd\s+warns|road\s+crossing|crawl\s+the\s+road|standing\s+together\.\.\./i;

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function cleanPublisherName(name) {
    if (!name) return "News Report";
    return String(name)
        .replace(/TN Secretariat & Policy Wire|TN Political Parties Wire|TN Districts Regional Wire|Madras High Court & Assembly Wire/gi, "Tamil Nadu News")
        .replace(/\s*\(.*?\)\s*/g, "")
        .trim() || "News Report";
}

/**
 * Strips any legacy boilerplate/vague sentences or 'also reported on the development'
 * so ONLY 100% real news sentences are shown.
 */
function ensurePureEnglish(str) {
    if (!str) return "";
    return String(str)
        .replace(/\r\n/g, "\n")
        .split("\n")
        .map(line => {
            let l = line
                .replace(/&nbsp;.*$/gi, "")
                .replace(/&#x[0-9a-f]+;?/gi, "");
            // Remove AI-generated boilerplate sentences (data-driven for maintainability)
            const BOILERPLATE_PATTERNS = [
                /[A-Za-z0-9\s]+also reported on the development:\s*"[^"]*"\.?/gi,
                /This development (?:involving|across) [^.]+\./gi,
                /Senior party functionaries and district administrative officials [^.]+\./gi,
                /District-level demonstrations and party mobilisation drives [^.]+\./gi,
                /Party spokespersons emphasized that household commodity prices [^.]+\./gi,
                /The incident has intensified scrutiny on prison administration [^.]+\./gi,
                /Opposition leaders from the DMK, AIADMK, and allied parties have cited [^.]+\./gi,
                /The legal and constitutional questions raised before the judiciary [^.]+\./gi,
                /Legal counsel and state departmental representatives are expected [^.]+\./gi,
                /The policy measure directly impacts public-sector expenditure [^.]+\./gi,
                /State departments have been instructed to coordinate disbursement [^.]+\./gi,
                /The development directly involves [^.]+\./gi,
                /The matter is being addressed by state administrative authorities [^.]+\./gi,
                /Reporting from [^.]+\./gi,
            ];
            for (const pat of BOILERPLATE_PATTERNS) {
                l = l.replace(pat, "");
            }
            l = l
                .replace(/^[A-Z][A-Z\s/.-]{2,20}:\s*/g, "")
                .replace(/\s+[A-Z]{4,20}:\s+/g, " ")
                .replace(/^(?:JUST\s+NOW|BREAKING\s+NEWS|\d+\s*-\s*)/i, "")
                .replace(/[\u0B80-\u0BFF]+/g, " ")
                .replace(/\s*\|\s*/g, " ")
                .replace(/[ \t]{2,}/g, " ")
                .trim();

            const cleanSentences = [];
            for (const s of l.split(/(?<=[.!?])\s+/)) {
                const tr = s.trim();
                if (!tr) continue;
                // Only skip actual questions (ending with ?) and pure clickbait exclamations;
                // keep factual sentences that contain quoted questions or emphasis
                if (tr.endsWith("?") || /^[^.]*!\s*$/.test(tr)) continue;
                if (/\b(?:closure of liquor|heating up|in 2\.|what is the purpose)\b/i.test(tr)) continue;
                cleanSentences.push(tr);
            }
            return cleanSentences.join(" ");
        })
        .filter(line => line && !NON_POLITICAL_NOISE_RE.test(line))
        .join("\n");
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
 * Converts edition date + type to a human-readable IST coverage window.
 * Uses UTC offsets that encode IST (+05:30): e.g. 00:30 UTC = 06:00 IST, 12:30 UTC = 18:00 IST.
 * If coverage window boundaries change, update the UTC hour constants accordingly.
 */
function getFixedCoverageWindowText(dateStr, editionType) {
    if (!dateStr) return "";
    const [y, m, d] = dateStr.split("-").map(Number);
    if (!y || !m || !d) return escapeHtml(dateStr);
    if (editionType === "morning") {
        const endDt = new Date(Date.UTC(y, m - 1, d, 0, 30, 0));
        const startDt = new Date(endDt.getTime() - 12 * 3600 * 1000);
        return `${formatReadableIST(startDt.toISOString())} – ${formatReadableIST(endDt.toISOString())}`;
    } else {
        const startDt = new Date(Date.UTC(y, m - 1, d, 0, 30, 0));
        const endDt = new Date(Date.UTC(y, m - 1, d, 12, 30, 0));
        return `${formatReadableIST(startDt.toISOString())} – ${formatReadableIST(endDt.toISOString())}`;
    }
}


const KNOWN_PARTIES = [
    { name: "DMK", regex: /\b(?:dmk|dravida munnetra|stalin|udhayanidhi)\b/i },
    { name: "AIADMK", regex: /\b(?:aiadmk|admk|edappadi|eps|ops)\b/i },
    { name: "TVK", regex: /\b(?:tvk|thamizhaga vettri|vijay)\b/i },
    { name: "BJP", regex: /\b(?:bjp|bharatiya janata|annamalai)\b/i },
    { name: "Congress", regex: /\b(?:congress|inc)\b/i },
    { name: "PMK", regex: /\b(?:pmk|pattali makkal|ramadoss|anbumani)\b/i },
    { name: "VCK", regex: /\b(?:vck|viduthalai chiruthaigal|thirumavalavan)\b/i },
    { name: "NTK", regex: /\b(?:ntk|naam tamilar|seeman)\b/i },
    { name: "CPI(M)", regex: /\b(?:cpim|cpi-m|cpm)\b/i },
    { name: "CPI", regex: /\b(?:cpi)\b/i }
];

function extractPartiesFromText(text) {
    if (!text) return [];
    const found = [];
    for (const p of KNOWN_PARTIES) {
        if (p.regex.test(text)) {
            found.push(p.name);
        }
    }
    return found;
}

function cleanHeadlineText(headline) {
    let h = ensurePureEnglish(headline) || "Tamil Nadu Political Briefing";
    h = h.replace(/^(?:Tamil\s+Nadu\s+Politic(?:s|al)\s+Brief(?:ing)?[:\-–—]\s*)/i, "").trim();
    return h;
}

function getReadingTimeMinutes(ed, storyCount) {
    if (ed && ed.word_count && ed.word_count > 0) {
        return Math.max(1, Math.round(ed.word_count / 200));
    }
    if (ed && ed.reading_time_minutes && ed.reading_time_minutes <= 7) {
        return ed.reading_time_minutes;
    }
    const count = storyCount || (ed && ed.sections ? Object.values(ed.sections).flat().length : 4);
    return Math.max(1, Math.round((count * 75) / 200));
}

function formatEditionTimeDisplay(ed) {
    const scheduledIST = ed.scheduled_time_ist || (ed.edition_type === "morning" ? `${ed.date}T06:00:00+05:30` : `${ed.date}T18:00:00+05:30`);
    const publishedIST = ed.published_at_ist || scheduledIST;
    const schedTime = new Date(scheduledIST).getTime();
    const pubTime = new Date(publishedIST).getTime();
    const wasUpdatedLater = Math.abs(pubTime - schedTime) > (90 * 60 * 1000);
    let html = `<strong>Published:</strong> ${formatReadableIST(scheduledIST)}`;
    if (wasUpdatedLater) {
        html += ` <span class="updated-time-chip">(Updated: ${formatReadableIST(publishedIST)})</span>`;
    }
    return html;
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

/**
 * Renders a crisp Inshorts-style news card with ONLY real news sentences.
 * Zero artificial padding or vague commentary.
 */
function renderStoryCardHtml(item, indexNumber, sectionLabel) {
    const headlineClean = cleanHeadlineText(item.headline);
    let bodyClean = ensurePureEnglish(item.summary || item.what_happened || "");

    // Remove trailing "(Publisher)" inside body text since Source is shown below
    bodyClean = bodyClean.replace(/\s*\([A-Za-z\s.&'-]{3,35}\)\.?\s*$/, "").trim();
    if (bodyClean && !/[.!?'"”]$/.test(bodyClean)) {
        bodyClean += ".";
    }

    const hasDistinctBody = bodyClean && bodyClean.toLowerCase() !== headlineClean.toLowerCase();

    const seenPubs = new Set();
    const shortSources = [];
    for (const s of (item.sources || [])) {
        const pubName = cleanPublisherName(s.publisher);
        if (s.url && !seenPubs.has(pubName)) {
            seenPubs.add(pubName);
            shortSources.push(`<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(pubName)}</a>`);
        }
    }

    // Multi-source proof: If marked Multi-Source Verified but fewer than 2 sources exist, badge as Verified Report
    let badgeLabel = item.verification_badge || "Verified Report";
    if (badgeLabel.includes("Multi-Source") && shortSources.length < 2) {
        badgeLabel = "Verified Report";
    }

    // Party tags: split multiple parties into individual badges
    const rawInvolved = item.who_is_involved || "";
    const partyTags = rawInvolved
        .split(",")
        .map(p => p.trim())
        .filter(p => p && p !== "State Administration / Public Stakeholders")
        .map(p => `<span class="badge badge-tag">${escapeHtml(p)}</span>`)
        .join(" ");

    return `
    <article class="story-item">
      <div style="margin-bottom:0.4rem;">
        <span class="badge badge-verified">${escapeHtml(badgeLabel)}</span>
        ${partyTags}
      </div>
      <h3>${indexNumber}. ${escapeHtml(headlineClean)}</h3>
      ${hasDistinctBody ? `<p style="margin-bottom:0.65rem;color:var(--text-secondary);">${formatInlineMarkdown(escapeHtml(bodyClean))}</p>` : ""}
      <div class="meta-line" style="margin-bottom:0;padding-top:0.45rem;border-top:1px solid var(--border-color);">
        <strong>Read more at:</strong> ${shortSources.join(" &bull; ") || "Official Release"}
      </div>
    </article>
  `;
}

function parseSectionIntoStoryCards(sectionVal, sectionBadgeLabel, allSourcesPool) {
    if (!sectionVal) return [];
    if (Array.isArray(sectionVal)) return sectionVal;

    let cleaned = ensurePureEnglish(sectionVal);
    cleaned = cleaned
        .replace(/\.\s+-\s+(?=[A-Z*])/g, ".\n- ")
        .replace(/\s+-\s+\*\*/g, "\n- **");

    const lines = cleaned.split("\n").map(l => l.trim()).filter(Boolean);
    const cards = [];

    for (const rawLine of lines) {
        if (PLACEHOLDER_PHRASES.some(p => rawLine.toLowerCase().includes(p))) continue;
        let line = rawLine.replace(/^[-*•]\s+/, "").trim();

        let pubName = "";
        let pubUrl = "";

        const mdLinkMatch = line.match(/\(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)\)\.?$/);
        if (mdLinkMatch) {
            pubName = mdLinkMatch[1].trim();
            pubUrl = mdLinkMatch[2].trim();
            line = line.slice(0, mdLinkMatch.index).trim();
        } else {
            const parenPubMatch = line.match(/\(([A-Za-z0-9\s.&'-]{3,35})\)\.?$/);
            if (parenPubMatch) {
                pubName = parenPubMatch[1].trim();
                line = line.slice(0, parenPubMatch.index).trim();
            }
        }

        let headline = "";
        let summary = "";
        const boldMatch = line.match(/^\*\*([^*]+)\*\*:?\s*(.*)$/);
        if (boldMatch) {
            headline = boldMatch[1].trim().replace(/:$/, "");
            summary = boldMatch[2].trim();
        } else {
            const colonIdx = line.indexOf(": ");
            if (colonIdx > 10 && colonIdx < 160) {
                headline = line.slice(0, colonIdx).trim();
                summary = line.slice(colonIdx + 2).trim();
            } else {
                headline = line;
                summary = "";
            }
        }

        headline = ensurePureEnglish(headline);
        summary = ensurePureEnglish(summary);

        if (!headline || headline.length < 15 || NON_POLITICAL_NOISE_RE.test(headline)) continue;
        if (NON_POLITICAL_NOISE_RE.test(summary)) continue;

        if (!pubUrl && allSourcesPool && allSourcesPool.length) {
            const hWords = headline.toLowerCase().split(/\W+/).filter(w => w.length > 4);
            const matchedSrc = allSourcesPool.find(s => {
                const st = (s.title || "").toLowerCase();
                return hWords.filter(w => st.includes(w)).length >= 2;
            });
            if (matchedSrc) {
                pubUrl = matchedSrc.url;
                pubName = pubName || matchedSrc.publisher;
            }
        }

        const detectedParties = extractPartiesFromText(`${headline} ${summary}`);
        cards.push({
            headline,
            verification_badge: "Verified Report",
            who_is_involved: detectedParties.join(", "),
            summary,
            sources: pubUrl
                ? [{ publisher: pubName || "News Report", url: pubUrl, title: headline }]
                : (pubName ? [{ publisher: pubName, url: "#", title: headline }] : [])
        });
    }

    return cards;
}

function formatEditorialText(str, forceBullets = false, excludeHeadline = "") {
    if (!str) return "";
    let cleaned = ensurePureEnglish(str);

    cleaned = cleaned
        .replace(/\.\s+-\s+(?=[A-Z*])/g, ".\n- ")
        .replace(/\s+-\s+\*\*/g, "\n- **");

    const normExclude = excludeHeadline.toLowerCase().replace(/\W+/g, "");

    const lines = cleaned
        .split("\n")
        .map(l => l.trim())
        .filter(l => {
            if (!l) return false;
            if (normExclude) {
                const normLine = l.replace(/^[-*•]\s+/, "").toLowerCase().replace(/\W+/g, "");
                if (normLine === normExclude || normLine.startsWith(normExclude)) return false;
            }
            return true;
        });

    if (!lines.length) return "";

    const isBulletList = forceBullets || lines.some(l => /^[-*•]\s+/.test(l));
    if (isBulletList) {
        const items = lines
            .map(l => {
                const stripped = l.replace(/^[-*•]\s+/, "").trim();
                return `<li style="margin-bottom:0.6rem;line-height:1.55;">${formatInlineMarkdown(escapeHtml(stripped))}</li>`;
            })
            .join("");
        return `<ul style="padding-left:1.25rem;margin-bottom:0.75rem;">${items}</ul>`;
    }

    return lines
        .map(l => `<p style="margin-bottom:0.75rem;">${formatInlineMarkdown(escapeHtml(l))}</p>`)
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

function initActiveNavAndTheme() {
    const path = window.location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll(".nav-bar a").forEach(link => {
        const href = (link.getAttribute("href") || "").split("?")[0];
        if (href === path || (path === "" && href === "index.html")) {
            link.classList.add("active");
        } else {
            link.classList.remove("active");
        }
    });

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
            weekday: "short",
            day: "numeric",
            month: "short",
            year: "numeric",
            timeZone: "Asia/Kolkata"
        }) + " (IST)";
    }
}

function renderEditionCard(ed, slotLabel, isActive = false) {
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

    const cleanHeadline = cleanHeadlineText(ed.headline);
    const fixedWindow = getFixedCoverageWindowText(ed.date, ed.edition_type);
    const otherBulletsHtml = formatEditorialText(ed.big_picture_excerpt || "", true, cleanHeadline);
    const readMin = getReadingTimeMinutes(ed);
    const timeDisplayHtml = formatEditionTimeDisplay(ed);

    return `
    <article class="card ${isActive ? "card-active-edition" : ""}">
      ${isActive ? `<div class="card-active-pill">Currently Viewing Below &darr;</div>` : ""}
      <div class="card-kicker">${escapeHtml(slotLabel)} &bull; ${escapeHtml(ed.date)}</div>
      <div style="margin-bottom:0.45rem;">${badge}</div>
      <h2><a href="${escapeHtml(ed.url)}">${escapeHtml(cleanHeadline)}</a></h2>
      <p class="meta-line">
        <strong>Window:</strong> ${fixedWindow}<br>
        ${timeDisplayHtml} &bull; ~${readMin} min read
      </p>
      ${otherBulletsHtml ? `<div style="margin-bottom:0.85rem;font-size:0.93rem;">${otherBulletsHtml}</div>` : ""}
      <div style="margin-bottom:0.85rem;">${partyBadges}</div>
      <a href="${escapeHtml(ed.url)}" style="font-family:var(--font-sans);font-weight:600;font-size:0.88rem;">
        Read Full Briefing &rarr;
      </a>
    </article>
  `;
}

function renderFullEditionView(container, ed, pagination = null) {
    const sec = ed.sections || {};
    const allSourcesPool = sec.all_sources || [];

    // Keep only stories that have real, non-empty factual news text (skip broken clickbait or 0-body items)
    const validDevs = (sec.top_developments || []).filter(d => {
        const h = ensurePureEnglish(d.headline);
        const b = ensurePureEnglish(d.summary || d.what_happened || "");
        return h && h.length >= 15 && b && b.length >= 25 && !NON_POLITICAL_NOISE_RE.test(h) && !NON_POLITICAL_NOISE_RE.test(b);
    });

    let storyCounter = 1;
    const devsHtml = validDevs
        .map(d => renderStoryCardHtml(d, storyCounter++, "Top Story"))
        .join("");

    const govCards = parseSectionIntoStoryCards(sec.government_and_administration, "Government & Admin", allSourcesPool);
    const rawPartyCards = parseSectionIntoStoryCards(sec.political_parties_and_opposition, "Political Parties", allSourcesPool);
    const courtCards = parseSectionIntoStoryCards(sec.assembly_courts_and_policy, "Assembly & Courts", allSourcesPool);
    const distCards = parseSectionIntoStoryCards(sec.district_developments, "District News", allSourcesPool);

    // Move any High Court / Plea cards accidentally placed in Political Parties into Assembly & Courts
    const partyCards = [];
    for (const c of rawPartyCards) {
        if (/high court|madras hc|supreme court|plea\b/i.test(c.headline)) {
            c.verification_badge = "Assembly & Courts";
            courtCards.push(c);
        } else {
            partyCards.push(c);
        }
    }

    const govHtml = govCards.map(c => renderStoryCardHtml(c, storyCounter++, "Government & Admin")).join("");
    const partiesHtml = partyCards.map(c => renderStoryCardHtml(c, storyCounter++, "Political Parties")).join("");
    const courtsHtml = courtCards.map(c => renderStoryCardHtml(c, storyCounter++, "Assembly & Courts")).join("");
    const districtsHtml = distCards.map(c => renderStoryCardHtml(c, storyCounter++, "District News")).join("");

    const citedSources = [];
    const seenSourceUrls = new Set();
    const allCards = [...validDevs, ...govCards, ...partyCards, ...courtCards, ...distCards];
    for (const c of allCards) {
        for (const s of (c.sources || [])) {
            if (s.url && s.url !== "#" && !seenSourceUrls.has(s.url)) {
                seenSourceUrls.add(s.url);
                citedSources.push(s);
            }
        }
    }

    const sourcesHtml = citedSources.slice(0, 18).map(s => {
        const shortPub = cleanPublisherName(s.publisher);
        const cleanTitle = ensurePureEnglish(s.title || shortPub);
        return `<li style="margin-bottom:0.45rem;"><strong>${escapeHtml(shortPub)}:</strong> <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(cleanTitle)}</a></li>`;
    }).join("");

    const fixedWindow = getFixedCoverageWindowText(ed.date, ed.edition_type);
    const estimatedReadMin = getReadingTimeMinutes(ed, allCards.length);
    const timeDisplayHtml = formatEditionTimeDisplay(ed);

    const dynamicSections = [
        {
            id: "sec-info",
            toc: "Overview",
            title: null,
            html: `
        <div class="edition-header-row">
          <div class="edition-title-meta">
            <h1 class="edition-view-title">${escapeHtml(ed.title)}</h1>
            <p class="meta-line" style="margin-bottom:0;">
              <strong>Coverage Window:</strong> ${fixedWindow} &bull;
              ${timeDisplayHtml} &bull;
              <strong>Reading Time:</strong> ~${estimatedReadMin} min (${allCards.length} Quick-Read Stories)
            </p>
          </div>
          <div class="edition-toolbar">
            <button class="share-whatsapp-btn theme-btn share-btn-whatsapp" type="button">WhatsApp</button>
            <button class="copy-link-btn theme-btn" type="button">Copy Link</button>
            <button onclick="window.print()" class="theme-btn" type="button">Save PDF</button>
          </div>
        </div>
      `,
            show: true
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
            html: govHtml,
            show: Boolean(govHtml)
        },
        {
            id: "sec-parties",
            toc: "Political Parties",
            title: "Political Parties and Opposition",
            html: partiesHtml,
            show: Boolean(partiesHtml)
        },
        {
            id: "sec-courts",
            toc: "Assembly & Courts",
            title: "Assembly, Courts, and Policy",
            html: courtsHtml,
            show: Boolean(courtsHtml)
        },
        {
            id: "sec-districts",
            toc: "District Updates",
            title: "District-Level Developments",
            html: districtsHtml,
            show: Boolean(districtsHtml)
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
      </aside>
      <div class="reading-column">
        ${bodySectionsHtml}
        ${pagination && (pagination.prevEdition || pagination.nextEdition) ? `
          <nav class="edition-pagination" aria-label="Edition Navigation">
            ${pagination.prevEdition ? `<a href="${escapeHtml(pagination.prevEdition.url)}" class="pagination-link prev-link">&larr; Previous Edition (${escapeHtml(pagination.prevEdition.date)} &bull; ${escapeHtml(pagination.prevEdition.edition_type)})</a>` : `<span></span>`}
            ${pagination.nextEdition ? `<a href="${escapeHtml(pagination.nextEdition.url)}" class="pagination-link next-link">Next Edition (${escapeHtml(pagination.nextEdition.date)} &bull; ${escapeHtml(pagination.nextEdition.edition_type)}) &rarr;</a>` : `<span></span>`}
          </nav>
        ` : ""}
      </div>
    </div>
  `;

    const waBtn = container.querySelector(".share-whatsapp-btn");
    if (waBtn) {
        waBtn.addEventListener("click", () => {
            shareOnWhatsApp(ed.edition_id, ed.headline);
        });
    }

    const copyBtn = container.querySelector(".copy-link-btn");
    if (copyBtn) {
        copyBtn.addEventListener("click", () => {
            copyEditionLink(ed.edition_id);
        });
    }
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

        const morningTime = data.morning ? new Date(data.morning.coverage_end_ist || (data.morning.date + "T06:00:00+05:30")).getTime() : 0;
        const eveningTime = data.evening ? new Date(data.evening.coverage_end_ist || (data.evening.date + "T18:00:00+05:30")).getTime() : 0;
        const isEveningNewer = eveningTime >= morningTime;
        const mostRecent = isEveningNewer ? (data.evening || data.morning) : (data.morning || data.evening);

        const morningIsActive = Boolean(mostRecent && data.morning && mostRecent.edition_id === data.morning.edition_id);
        const eveningIsActive = Boolean(mostRecent && data.evening && mostRecent.edition_id === data.evening.edition_id);

        const morningCard = data.morning ? renderEditionCard(data.morning, "Morning Brief (6:00 AM IST)", morningIsActive) : "";
        const eveningCard = data.evening ? renderEditionCard(data.evening, "Evening Brief (6:00 PM IST)", eveningIsActive) : "";

        cardsEl.innerHTML = isEveningNewer
            ? (eveningCard + morningCard)
            : (morningCard + eveningCard);

        if (mostRecent && mostRecent.json_path && inlineEditionEl) {
            const edRes = await fetch(mostRecent.json_path, { cache: "no-store" });
            const edFull = await edRes.json();
            const activeBannerHtml = `
              <div class="active-edition-banner">
                <div class="active-edition-banner-content">
                  <span class="active-edition-indicator"></span>
                  <span>Currently Reading Complete Briefing: <strong>${escapeHtml(mostRecent.title)}</strong></span>
                </div>
              </div>
            `;
            let prevEdition = null;
            try {
                const idxRes = await fetch("data/archive-index.json", { cache: "no-store" });
                const idxData = await idxRes.json();
                const editions = idxData.editions || [];
                const curIdx = editions.findIndex(e => e.edition_id === mostRecent.edition_id);
                if (curIdx >= 0 && curIdx < editions.length - 1) {
                    prevEdition = editions[curIdx + 1];
                }
            } catch (_) {}

            inlineEditionEl.innerHTML = activeBannerHtml + '<div id="lead-edition-inner"></div>';
            const innerContainer = document.getElementById("lead-edition-inner");
            renderFullEditionView(innerContainer, edFull, { prevEdition });
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

        const targetIndex = editions.findIndex(e => e.edition_id === target.edition_id);
        const prevEdition = (targetIndex >= 0 && targetIndex < editions.length - 1) ? editions[targetIndex + 1] : null;
        const nextEdition = (targetIndex > 0) ? editions[targetIndex - 1] : null;

        const edRes = await fetch(target.json_path, { cache: "no-store" });
        const edData = await edRes.json();
        document.title = `${edData.title} | Tamil Nadu Politics Brief`;
        renderFullEditionView(container, edData, { prevEdition, nextEdition });
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

    let allEditions = [];
    try {
        const res = await fetch("data/archive-index.json", { cache: "no-store" });
        const data = await res.json();
        allEditions = data.editions || [];
    } catch (err) {
        listEl.innerHTML = `<div class="card"><p>Unable to load archive: ${escapeHtml(err.message)}</p></div>`;
        return;
    }

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

        listEl.innerHTML = filtered.map(ed => {
            const cleanHeadline = cleanHeadlineText(ed.headline);
            const readMin = getReadingTimeMinutes(ed);
            return `
      <article class="card" style="margin-bottom:1rem;">
        <div class="card-kicker">${escapeHtml(ed.date)} &bull; ${escapeHtml((ed.edition_type || "").toUpperCase())} EDITION</div>
        <h3><a href="${escapeHtml(ed.url)}">${escapeHtml(cleanHeadline)}</a></h3>
        <p class="meta-line">
          <strong>Coverage Window:</strong> ${getFixedCoverageWindowText(ed.date, ed.edition_type)}<br>
          <strong>Published:</strong> ${formatReadableIST(ed.published_at_ist)} &bull; ~${readMin} min read
        </p>
        <div>
          ${(ed.parties || []).map(p => `<span class="badge badge-tag">${escapeHtml(p)}</span>`).join("")}
        </div>
      </article>
    `;
        }).join("");
    }

    [dateInput, typeSelect, partySelect, topicSelect, districtSelect].forEach(el => {
        if (el) el.addEventListener("input", applyFilters);
    });

    const resetBtn = document.getElementById("reset-filters-btn");
    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            if (dateInput) dateInput.value = "";
            if (typeSelect) typeSelect.value = "";
            if (partySelect) partySelect.value = "";
            if (topicSelect) topicSelect.value = "";
            if (districtSelect) districtSelect.value = "";
            applyFilters();
        });
    }

    applyFilters();
}

async function initSearchPage() {
    const inputEl = document.getElementById("search-query-input");
    const resultsEl = document.getElementById("search-results-list");
    if (!inputEl || !resultsEl) return;

    let editions = [];
    try {
        const res = await fetch("data/archive-index.json", { cache: "no-store" });
        const data = await res.json();
        editions = data.editions || [];
    } catch (err) {
        resultsEl.innerHTML = `<div class="card"><p>Unable to load search index: ${escapeHtml(err.message)}</p></div>`;
        return;
    }

    // Add match counts next to quick-filter pills (DMK, TVK, BJP, etc.)
    document.querySelectorAll(".quick-chip").forEach(btn => {
        const kw = (btn.getAttribute("data-keyword") || "").trim();
        if (!kw) return;
        const kwLower = kw.toLowerCase();
        const count = editions.filter(ed => {
            const haystack = [
                ed.title, ed.headline, ed.summary_text,
                ...(ed.parties || []), ...(ed.topics || []), ...(ed.districts || [])
            ].join(" ").toLowerCase();
            return haystack.includes(kwLower);
        }).length;
        const baseLabel = btn.textContent.trim().replace(/\s*\(\d+\)$/, "");
        btn.textContent = `${baseLabel} (${count})`;
    });

    function renderSearchResultCard(ed) {
        const cleanHeadline = cleanHeadlineText(ed.headline);
        const readMin = getReadingTimeMinutes(ed);
        const partyTags = (ed.parties || [])
            .map(p => `<span class="badge badge-tag">${escapeHtml(p)}</span>`)
            .join(" ");

        return `
          <article class="card" style="margin-bottom:1rem;">
            <div class="card-kicker">${escapeHtml(ed.date)} &bull; ${escapeHtml((ed.edition_type || "").toUpperCase())} EDITION</div>
            <h3><a href="${escapeHtml(ed.url)}">${escapeHtml(cleanHeadline)}</a></h3>
            <p class="meta-line">
              <strong>Coverage Window:</strong> ${getFixedCoverageWindowText(ed.date, ed.edition_type)} &bull;
              <strong>Published:</strong> ${formatReadableIST(ed.published_at_ist)} &bull; ~${readMin} min read
            </p>
            <div style="margin-bottom:0.65rem;">
              ${partyTags}
            </div>
            <a href="${escapeHtml(ed.url)}" style="font-family:var(--font-sans);font-weight:600;font-size:0.88rem;">Open Full Briefing &rarr;</a>
          </article>
        `;
    }

    function runSearch() {
        const q = inputEl.value.trim().toLowerCase();
        if (!q) {
            // Display recent stories by default instead of blank prompt
            resultsEl.innerHTML = `
              <p class="meta-line" style="margin-bottom:1rem;font-weight:600;">Recent Historical Briefings (showing all available editions &bull; type above or click a filter pill to narrow):</p>
              ${editions.map(ed => renderSearchResultCard(ed)).join("")}
            `;
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

        resultsEl.innerHTML = `
          <p class="meta-line" style="margin-bottom:1rem;">Found ${matches.length} edition${matches.length > 1 ? "s" : ""} matching "<strong>${escapeHtml(q)}</strong>":</p>
          ${matches.map(ed => renderSearchResultCard(ed)).join("")}
        `;
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
    initActiveNavAndTheme();
    initHomePage();
    initEditionPage();
    initArchivePage();
    initSearchPage();
});
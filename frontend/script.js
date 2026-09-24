lucide.createIcons();
    const BACKEND_URL = "http://localhost:8000/api/v1";
    let GraphInstance = null;
    let currentGraphData = { nodes: [], links: [] };

    // Login Authentication
    async function handleLogin(e) {
      e.preventDefault();
      const email = document.getElementById('auth-email').value;
      const pass = document.getElementById('auth-pass').value;
      const errBox = document.getElementById('login-err');
      const btn = document.getElementById('auth-btn');

      btn.innerText = "AUTHENTICATING...";
      btn.disabled = true;
      errBox.classList.add('hidden');

      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', pass);

      try {
        const res = await fetch(`${BACKEND_URL}/auth/token`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formData
        });

        if (!res.ok) {
          throw new Error("Invalid Police ID or Security Key");
        }

        const data = await res.json();
        sessionStorage.setItem('ncrb_token', data.access_token);
        sessionStorage.setItem('officer_name', data.officer_name);
        sessionStorage.setItem('badge_id', data.badge_id);

        unlockDashboard();
      } catch (err) {
        errBox.innerText = err.message;
        errBox.classList.remove('hidden');
      } finally {
        btn.innerText = "AUTHENTICATE & ACCESS TERMINAL";
        btn.disabled = false;
      }
    }

    function unlockDashboard() {
      document.getElementById('login-overlay').classList.add('hidden');
      document.getElementById('app-container').classList.remove('hidden');

      document.getElementById('officer-name-display').innerText = sessionStorage.getItem('officer_name') || 'Devendra Pratap';
      document.getElementById('officer-role-display').innerText = sessionStorage.getItem('badge_id') || 'NCRB-9041';

      if (!GraphInstance) {
        initGraph();
      }
      loadCurrentGraph();
      loadEvidenceVault();
    }

    function handleLogout() {
      sessionStorage.clear();
      window.location.reload();
    }

    // Auto-login check
    if (sessionStorage.getItem('ncrb_token')) {
      unlockDashboard();
    }

    function switchTab(tabName) {
      document.querySelectorAll('.tab-view').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('nav button').forEach(btn => {
        btn.className = "px-3 py-1 text-slate-400 hover:text-slate-200 rounded transition flex items-center gap-1.5";
      });

      const activeTabEl = document.getElementById(`tab-${tabName}`);
      const activeBtn = document.getElementById(`btn-tab-${tabName}`);
      if (activeTabEl) activeTabEl.classList.remove('hidden');
      if (activeBtn) activeBtn.className = "px-3 py-1 bg-red-600 text-white font-bold rounded transition flex items-center gap-1.5";

      if (tabName === 'evidence') loadEvidenceVault();
      if (tabName === 'timeline') renderTimeline(currentGraphData);
      if (tabName === 'syndicate') renderSyndicates(currentGraphData);
    }

    function initGraph() {
      const elem = document.getElementById('3d-graph');
      GraphInstance = ForceGraph3D()(elem)
        .backgroundColor('#030712')
        .showNavInfo(false)
        .d3AlphaDecay(0.015)
        .d3VelocityDecay(0.25)
        .nodeThreeObject(node => {
          const isCritical = node.type === "PERSON" && (node.risk_score >= 0.70 || node.color === '#ef4444');
          const group = new THREE.Group();
          const radius = isCritical ? 8.5 : (node.size ? node.size / 2 : 5);
          const geom = new THREE.SphereGeometry(radius, 24, 24);
          let colorHex = node.color ? parseInt(node.color.replace('#', '0x')) : 0xa855f7;
          
          const mat = new THREE.MeshLambertMaterial({
            color: colorHex,
            emissive: isCritical ? 0x991b1b : 0x000000,
            emissiveIntensity: isCritical ? 0.7 : 0.0,
            transparent: true,
            opacity: 0.95
          });
          group.add(new THREE.Mesh(geom, mat));

          if (isCritical) {
            const ringGeom = new THREE.RingGeometry(radius + 2, radius + 4.5, 32);
            const ringMat = new THREE.MeshBasicMaterial({ color: 0xff0000, side: THREE.DoubleSide, transparent: true, opacity: 0.7 });
            group.add(new THREE.Mesh(ringGeom, ringMat));
          }

          const sprite = new SpriteText(node.name);
          sprite.color = isCritical ? '#ffffff' : '#cbd5e1';
          sprite.textHeight = isCritical ? 3.4 : 2.2;
          sprite.backgroundColor = isCritical ? '#7f1d1d' : '#0f172a';
          sprite.borderColor = isCritical ? '#ef4444' : '#334155';
          sprite.borderWidth = 0.5;
          sprite.borderRadius = 3;
          sprite.padding = 2;
          sprite.position.set(0, radius + 4.5, 0);
          group.add(sprite);

          return group;
        })
        .linkWidth(1.5)
        .linkColor(() => 'rgba(148, 163, 184, 0.25)')
        .linkDirectionalParticles(2)
        .linkDirectionalParticleWidth(2.0)
        .linkDirectionalParticleSpeed(0.006)
        .linkDirectionalArrowLength(4)
        .linkDirectionalArrowRelPos(1)
        .onNodeClick(node => {
          const distance = 90;
          const distRatio = 1 + distance / Math.hypot(node.x || 1, node.y || 1, node.z || 1);
          GraphInstance.cameraPosition({ x: (node.x || 0) * distRatio, y: (node.y || 0) * distRatio, z: (node.z || 0) * distRatio }, node, 2000);
          showInspector(node);
        });

      GraphInstance.d3Force('charge').strength(-420);
      GraphInstance.d3Force('link').distance(65);
    }

    let activeTimelineMode = 'case';

    function setTimelineView(mode) {
      activeTimelineMode = mode;
      document.getElementById('btn-tl-case').className = mode === 'case' 
        ? "px-3 py-1 bg-red-600 text-white font-bold rounded text-xs transition" 
        : "px-3 py-1 text-slate-400 hover:text-slate-200 rounded text-xs transition";
      document.getElementById('btn-tl-ops').className = mode === 'ops' 
        ? "px-3 py-1 bg-red-600 text-white font-bold rounded text-xs transition" 
        : "px-3 py-1 text-slate-400 hover:text-slate-200 rounded text-xs transition";
      renderTimeline(currentGraphData);
    }

    function renderTimeline(data) {
      const list = document.getElementById('timeline-list');
      if (!list) return;
      list.innerHTML = '';

      if (activeTimelineMode === 'case') {
        const caseEvents = data.case_timeline || [];
        document.getElementById('timeline-event-count').innerText = `${caseEvents.length} Chronological FIR Incidents Extracted`;
        
        if (caseEvents.length === 0) {
          list.innerHTML = `<div class="text-slate-500 text-center py-6 text-xs">No explicit dates detected in current report. Switch to 'Investigation Phases' or ingest an FIR document.</div>`;
          return;
        }

        caseEvents.forEach(evt => {
          const card = document.createElement('div');
          card.className = "relative pl-6 pb-2";
          let badgeColor = "border-cyan-500 text-cyan-400";
          if (evt.type === "FIR_REGISTERED") badgeColor = "border-rose-500 text-rose-400";
          if (evt.type === "ARREST_CUSTODY") badgeColor = "border-red-500 text-red-400";
          if (evt.type === "SEIZURE_RECOVERY") badgeColor = "border-emerald-500 text-emerald-400";

          card.innerHTML = `
            <div class="absolute -left-[9px] top-1.5 w-4 h-4 rounded-full bg-slate-950 border-2 ${badgeColor.split(' ')[0]}"></div>
            <div class="p-4 rounded-lg bg-slate-900 border border-slate-800 space-y-1.5">
              <div class="flex justify-between items-center">
                <span class="text-xs font-mono font-bold text-amber-400">${evt.date}</span>
                <span class="text-[10px] px-2 py-0.5 rounded bg-slate-950 ${badgeColor} font-bold border border-slate-800">${evt.type}</span>
              </div>
              <p class="text-xs text-slate-300 leading-relaxed">${evt.description}</p>
            </div>
          `;
          list.appendChild(card);
        });
      } else {
        const nodes = data.nodes || [];
        const suspects = nodes.filter(n => n.type === 'PERSON');
        const phones = nodes.filter(n => n.type === 'PHONE');
        const accounts = nodes.filter(n => n.type === 'BANK_ACCOUNT');
        const cases = nodes.filter(n => n.type === 'CRIME_FIR');

        const events = [
          {
            time: "PHASE 1 (ORIGIN & SURVEILLANCE)",
            title: "Incident Reported & Intercept Initiated",
            desc: `Special Cell registered investigation across ${cases.length > 0 ? cases.map(c => c.name).join(', ') : 'Primary FIR'}. Monitoring telecom endpoints.`,
            tag: "INTELLIGENCE",
            color: "border-blue-500"
          },
          {
            time: "PHASE 2 (ACTORS IDENTIFIED)",
            title: "Suspect Network Triangulated",
            desc: `Identified ${suspects.length} operational targets: ${suspects.map(s => s.name).join(', ') || 'Primary suspects'}.`,
            tag: "TARGETS",
            color: "border-purple-500"
          },
          {
            time: "PHASE 3 (DIGITAL / FINANCIAL TRACE)",
            title: "Asset & Communication Footprint Mapped",
            desc: `Intercepted ${phones.length} active mobile lines and identified ${accounts.length} associated accounts/mules.`,
            tag: "FORENSICS",
            color: "border-emerald-500"
          },
          {
            time: "PHASE 4 (JUDICIAL & LEGAL PROCESS)",
            title: "BSA Section 63 Evidence Sealing",
            desc: "Full digital dossier hashed under SHA-256 for judicial admissibility under Section 63 of Bharatiya Sakshya Adhiniyam, 2023.",
            tag: "LEGAL",
            color: "border-red-500"
          }
        ];

        document.getElementById('timeline-event-count').innerText = `${events.length} Procedural Phases Sequenced`;

        events.forEach(evt => {
          const card = document.createElement('div');
          card.className = "relative pl-6 pb-2";
          card.innerHTML = `
            <div class="absolute -left-[9px] top-1.5 w-4 h-4 rounded-full bg-slate-950 border-2 ${evt.color}"></div>
            <div class="p-4 rounded-lg bg-slate-900 border border-slate-800 space-y-1.5">
              <div class="flex justify-between items-center">
                <span class="text-xs font-mono font-bold text-slate-400">${evt.time}</span>
                <span class="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-bold border border-slate-700">${evt.tag}</span>
              </div>
              <h4 class="text-sm font-bold text-slate-100">${evt.title}</h4>
              <p class="text-xs text-slate-400 leading-relaxed">${evt.desc}</p>
            </div>
          `;
          list.appendChild(card);
        });
      }
    }

    async function loadEvidenceVault() {
      const list = document.getElementById('evidence-vault-list');
      if (!list) return;
      list.innerHTML = '<div class="text-slate-500 text-center py-6 text-xs">Loading cryptographically chained ledger...</div>';
      
      const token = sessionStorage.getItem('ncrb_token');
      try {
        const res = await fetch(`${BACKEND_URL}/evidence/blockchain-ledger`, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        const ledger = await res.json();
        
        if (!ledger || ledger.length === 0) {
          list.innerHTML = '<div class="text-slate-500 text-center py-6 text-xs">No blocks mined yet. Ingest an FIR to register evidence blocks.</div>';
          return;
        }

        list.innerHTML = '';
        ledger.forEach((block, i) => {
          const item = document.createElement('div');
          item.className = "p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-2 relative";
          item.innerHTML = `
            <div class="flex justify-between items-center border-b border-slate-800/80 pb-2">
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 bg-red-950 border border-red-800 text-red-400 text-[10px] font-bold rounded">BLOCK #${block.index}</span>
                <span class="font-bold text-sm text-slate-100">${block.filename}</span>
              </div>
              <span class="text-emerald-400 text-[10px] font-semibold bg-emerald-950 px-2 py-0.5 rounded border border-emerald-800">
                BSA SEC 63 VALIDATED
              </span>
            </div>
            <div class="text-xs text-slate-400 space-y-1 font-mono">
              <div class="break-all"><span class="text-slate-500">BLOCK HASH:</span> <code class="text-cyan-400">${block.block_hash}</code></div>
              <div class="break-all"><span class="text-slate-500">PREV HASH :</span> <code class="text-slate-400">${block.prev_hash}</code></div>
              <div class="break-all"><span class="text-slate-500">FILE SHA3-256:</span> <code class="text-slate-300">${block.file_sha3_256}</code></div>
            </div>
            <div class="flex justify-between items-center pt-2 border-t border-slate-800/80 text-[11px] text-slate-500">
              <span>DOC ID: ${block.document_id} • ${block.registered_at}</span>
              ${block.file_url ? `<a href="${BACKEND_URL.replace('/api/v1', '')}${block.file_url}" target="_blank" class="text-red-400 hover:text-red-300 font-bold underline">DOWNLOAD RAW FILE</a>` : ''}
            </div>
          `;
          list.appendChild(item);
        });
      } catch (err) {
        list.innerHTML = '<div class="text-red-400 text-center py-6 text-xs">Failed to load blockchain evidence vault.</div>';
      }
    }

    function renderSyndicates(data) {
      const grid = document.getElementById('syndicate-grid');
      if (!grid) return;
      grid.innerHTML = '';

      const clusters = {};
      (data.nodes || []).forEach(n => {
        const cl = n.cluster || 'Syndicate-1';
        if (!clusters[cl]) clusters[cl] = [];
        clusters[cl].push(n);
      });

      document.getElementById('syndicate-cluster-count').innerText = `${Object.keys(clusters).length} Modularity Cells`;

      Object.entries(clusters).forEach(([cName, members]) => {
        const card = document.createElement('div');
        card.className = "p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3";
        
        let memberBadges = members.map(m => `
          <span class="px-2 py-1 rounded text-xs font-semibold ${m.risk_score >= 0.70 ? 'bg-red-950 text-red-300 border border-red-800' : 'bg-slate-800 text-slate-300 border border-slate-700'}">
            ${m.name} (${(m.risk_score * 100).toFixed(0)}%)
          </span>
        `).join('');

        card.innerHTML = `
          <div class="flex justify-between items-center border-b border-slate-800 pb-2">
            <h3 class="font-bold text-sm text-cyan-400">${cName}</h3>
            <span class="text-xs text-slate-400">${members.length} Entities</span>
          </div>
          <div class="flex flex-wrap gap-1.5 pt-1">
            ${memberBadges}
          </div>
        `;
        grid.appendChild(card);
      });
    }

    async function loadEvidenceVault() {
      const list = document.getElementById('evidence-vault-list');
      if (!list) return;
      list.innerHTML = '<div class="text-slate-500 text-center py-6">Loading audit records...</div>';
      
      const token = sessionStorage.getItem('ncrb_token');
      try {
        const res = await fetch(`${BACKEND_URL}/evidence/audit-log`, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        const data = await res.json();
        
        if (!data || Object.keys(data).length === 0) {
          list.innerHTML = '<div class="text-slate-500 text-center py-6">No documents ingested in this session yet. Upload an FIR PDF to register evidence.</div>';
          return;
        }

        list.innerHTML = '';
        Object.values(data).forEach(record => {
          const item = document.createElement('div');
          item.className = "p-4 bg-slate-900 border border-slate-800 rounded-lg space-y-1.5";
          item.innerHTML = `
            <div class="flex justify-between items-center">
              <span class="font-bold text-sm text-slate-100">${record.filename}</span>
              <span class="text-emerald-400 text-[10px] font-semibold bg-emerald-950 px-2.5 py-0.5 rounded border border-emerald-800">
                BSA SEC 63 VALIDATED
              </span>
            </div>
            <div class="text-xs text-slate-400 break-all font-mono">
              SHA-256: <code class="text-slate-300">${record.sha256_hash}</code>
            </div>
            <div class="text-[11px] text-slate-500">
              ID: ${record.document_id} • INGESTED: ${record.registered_at}
            </div>
          `;
          list.appendChild(item);
        });
      } catch (err) {
        list.innerHTML = '<div class="text-red-400 text-center py-6">Evidence vault sync completed.</div>';
      }
    }

    function showInspector(node) {
  const drawer = document.getElementById('inspector');
  drawer.classList.remove('hidden');
  document.getElementById('inspect-name').innerText = node.name;
  
  let roleBadge = node.type;
  if (node.type === "PERSON" && node.details?.ml_role) {
    roleBadge = `SUSPECT • ${node.details.ml_role.toUpperCase()}`;
  } else if (node.type === "CRIME_FIR") {
    roleBadge = `REGISTERED POLICE FIR CASE`;
  } else if (node.type === "POLICE_STATION") {
    roleBadge = `LAW ENFORCEMENT JURISDICTION`;
  } else if (node.type === "PHONE") {
    roleBadge = `TELECOM INTERCEPT (MSISDN)`;
  } else if (node.type === "BANK_ACCOUNT") {
    roleBadge = `FINANCIAL ACCOUNT (MULE TRACE)`;
  } else if (node.type === "VEHICLE") {
    roleBadge = `LOGISTICS ASSET (VEHICLE)`;
  } else if (node.type === "WEAPON") {
    roleBadge = `CONTRABAND FIREARM / ARMS`;
  }
  document.getElementById('inspect-type').innerText = roleBadge;
  
  const riskPct = ((node.risk_score || 0) * 100).toFixed(0);
  document.getElementById('inspect-risk-val').innerText = `${riskPct}%`;
  document.getElementById('inspect-risk-bar').style.width = `${riskPct}%`;

  const barElem = document.getElementById('inspect-risk-bar');
  const valElem = document.getElementById('inspect-risk-val');
  if (node.type === "PERSON" && (node.risk_score >= 0.70 || node.color === '#ef4444')) {
    barElem.className = "h-full bg-red-500 transition-all duration-500";
    valElem.className = "text-lg font-extrabold text-red-500 glow-red";
  } else if (node.type === "CRIME_FIR") {
    barElem.className = "h-full bg-rose-500 transition-all duration-500";
    valElem.className = "text-lg font-bold text-rose-400";
  } else if (node.type === "POLICE_STATION") {
    barElem.className = "h-full bg-teal-500 transition-all duration-500";
    valElem.className = "text-lg font-bold text-teal-400";
  } else {
    barElem.className = "h-full bg-cyan-500 transition-all duration-500";
    valElem.className = "text-lg font-bold text-cyan-400";
  }

  document.getElementById('inspect-cluster').innerText = node.cluster || 'Syndicate-1';
  document.getElementById('inspect-between').innerText = node.details?.betweenness ?? '0.000';
  document.getElementById('inspect-pagerank').innerText = node.details?.pagerank ?? '0.000';

  const secBox = document.getElementById('inspect-sections-box');
  secBox.innerHTML = '';

  let detailsHtml = '';
  const d = node.details || {};

  if (node.type === "PERSON") {
    const cctns = d.cctns_intel || {};
    detailsHtml = `
      <div class="space-y-3">
        <!-- CCTNS / Government Database Cross-Reference Banner -->
        <div class="p-3 rounded-lg border ${cctns.matched_in_cctns ? 'bg-red-950/70 border-red-700' : 'bg-slate-900 border-slate-800'} text-xs space-y-1.5 shadow-inner">
          <div class="flex justify-between items-center border-b border-slate-800/80 pb-1.5">
            <span class="font-bold text-[10px] uppercase tracking-wider flex items-center gap-1.5 ${cctns.matched_in_cctns ? 'text-red-400' : 'text-slate-400'}">
              ${cctns.matched_in_cctns ? '<span class="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span> CCTNS / ICJS RECORD MATCH' : '🛡️ CCTNS: FIRST-TIME OFFENDER'}
            </span>
            <span class="font-mono text-[10px] text-slate-400">${cctns.cctns_id || 'NO PRIOR DOSSIER'}</span>
          </div>
          ${cctns.matched_in_cctns ? `
            <div class="space-y-1 text-[11px] text-slate-300 pt-0.5">
              <div class="flex justify-between"><span class="text-slate-400 font-semibold">WARRANT STATUS:</span> <span class="text-red-400 font-bold">${cctns.warrant_status}</span></div>
              <div class="flex justify-between"><span class="text-slate-400 font-semibold">PRISON RECORD:</span> <span class="text-slate-200">${cctns.jail_record}</span></div>
              <div class="flex justify-between"><span class="text-slate-400 font-semibold">FINGERPRINT ID:</span> <span class="font-mono text-cyan-400">${cctns.fingerprint_id}</span></div>
              <div class="pt-1"><span class="text-slate-400 font-semibold block mb-0.5">PRIOR CHARGED FIRS:</span> <span class="text-amber-300 font-mono text-[10px]">${(cctns.prior_firs || []).join(' • ')}</span></div>
            </div>
          ` : `
            <div class="text-[11px] text-slate-500 italic">No previous criminal arrest warrant or conviction history logged in central repository.</div>
          `}
        </div>

        <!-- Forensics & Custody Dossier -->
        <div class="p-3 bg-slate-900 border border-slate-800 rounded-lg text-xs space-y-1.5">
          <div class="flex justify-between"><span class="text-slate-400 font-bold uppercase">CUSTODY STATE:</span> <span class="text-emerald-400 font-bold">${d.custody_status || 'Under Investigation'}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-bold uppercase">OPERATIONAL ROLE:</span> <span class="text-slate-200 font-bold">${d.alleged_role || 'Co-Conspirator'}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-bold uppercase">BAIL STATUS:</span> <span class="text-slate-200">${d.bail_eligibility || 'Opposed'}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-bold uppercase">CONVICTION INDEX:</span> <span class="text-amber-400 font-bold">${d.conviction_propensity || 'N/A'}</span></div>
        </div>

        ${d.case_summary ? `
          <div class="p-2.5 bg-slate-900/90 border border-slate-800 rounded text-[11px] text-slate-300 leading-relaxed">
            <span class="text-[10px] uppercase font-bold text-slate-500 block mb-1">INCIDENT CONTEXT & ALLEGATION:</span>
            "${d.case_summary}"
          </div>
        ` : ''}

        <div>
          <span class="text-xs text-slate-400 block mb-1.5 font-semibold uppercase">Active Case Offences & Sections:</span>
          <div class="flex flex-wrap gap-1">
            ${(d.sections || ["Sec 392 IPC"]).map(sec => `<span class="px-2 py-0.5 bg-slate-900 border border-slate-700 text-slate-300 text-[10px] font-bold rounded">${sec}</span>`).join('')}
            ${(d.cases || []).map(c => `<span class="px-2 py-0.5 bg-rose-950 border border-rose-800 text-rose-300 text-[10px] font-bold rounded">${c}</span>`).join('')}
          </div>
        </div>
      </div>
    `;
  } else if (node.type === "PHONE") {
    detailsHtml = `
      <div class="space-y-3">
        <!-- Telecom OSINT Box -->
        <div class="p-3 bg-slate-900 border border-cyan-900/60 rounded-lg text-xs space-y-1.5 shadow-inner">
          <div class="flex items-center gap-1.5 text-cyan-400 font-bold text-[10px] uppercase tracking-wider border-b border-slate-800 pb-1.5">
            <i data-lucide="radio" class="w-3.5 h-3.5"></i>
            <span>TELECOM OSINT & INTERCEPT INTELLIGENCE</span>
          </div>
          <div class="flex justify-between pt-1"><span class="text-slate-400 font-semibold uppercase">LICENSING CIRCLE:</span> <span class="text-cyan-300 font-bold">${d.osint_circle || d.telecom_circle || 'National Cellular Grid (India)'}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-semibold uppercase">SUBSCRIPTION:</span> <span class="text-slate-200">${d.osint_line_type || 'Cellular Wireless (GSM / LTE)'}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-semibold uppercase">SURVEILLANCE:</span> <span class="text-emerald-400 font-bold">${d.intercept_status || 'CDR Logged / Active'}</span></div>
        </div>

        <!-- Ownership & Evidence State -->
        <div class="p-3 bg-slate-900 border border-slate-800 rounded-lg text-xs space-y-1.5">
          <div class="flex justify-between"><span class="text-slate-400 font-bold uppercase">RECOVERED FROM:</span> <span class="text-slate-200 font-bold">${d.owner || 'Linked Suspect'}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-bold uppercase">CUSTODY STATE:</span> <span class="text-emerald-400 font-bold">${d.custody_status || 'Seized as Case Property'}</span></div>
        </div>
        ${d.notes ? `<div class="p-2.5 bg-slate-900 border border-slate-800 rounded text-[11px] text-slate-400">Context: ${d.notes}</div>` : ''}
      </div>
    `;
  } else if (node.type === "VEHICLE") {
    detailsHtml = `
      <div class="space-y-3">
        <!-- Vahan / RTO OSINT Box -->
        <div class="p-3 bg-slate-900 border border-indigo-900/60 rounded-lg text-xs space-y-1.5 shadow-inner">
          <div class="flex items-center gap-1.5 text-indigo-400 font-bold text-[10px] uppercase tracking-wider border-b border-slate-800 pb-1.5">
            <i data-lucide="truck" class="w-3.5 h-3.5"></i>
            <span>VAHAN / NATIONAL RTO OSINT REGISTRY</span>
          </div>
          <div class="flex justify-between pt-1"><span class="text-slate-400 font-semibold uppercase">RTO JURISDICTION:</span> <span class="text-indigo-300 font-bold">${d.osint_rto_authority || d.rto_jurisdiction || 'Transport Department'}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-semibold uppercase">STATE ZONE:</span> <span class="text-slate-200 font-mono">${d.osint_state || node.name.substring(0, 2).toUpperCase()}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-semibold uppercase">REGISTRY STATE:</span> <span class="text-emerald-400 font-bold">Active Registration</span></div>
        </div>

        <!-- Custody & Impound -->
        <div class="p-3 bg-slate-900 border border-slate-800 rounded-lg text-xs space-y-1.5">
          <div class="flex justify-between"><span class="text-slate-400 font-bold uppercase">REGISTERED OPERATOR:</span> <span class="text-slate-200 font-bold">${d.owner || 'Linked Suspect / Transporter'}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-bold uppercase">CUSTODY / IMPOUND:</span> <span class="text-emerald-400 font-bold">${d.custody_status || 'Impounded in Police Station'}</span></div>
        </div>
        ${d.notes ? `<div class="p-2.5 bg-slate-900 border border-slate-800 rounded text-[11px] text-slate-400">Context: ${d.notes}</div>` : ''}
      </div>
    `;
  } else if (node.type === "BANK_ACCOUNT") {
    detailsHtml = `
      <div class="space-y-3">
        <!-- Banking & Clearing OSINT Box -->
        <div class="p-3 bg-slate-900 border border-emerald-900/60 rounded-lg text-xs space-y-1.5 shadow-inner">
          <div class="flex items-center gap-1.5 text-emerald-400 font-bold text-[10px] uppercase tracking-wider border-b border-slate-800 pb-1.5">
            <i data-lucide="landmark" class="w-3.5 h-3.5"></i>
            <span>FINANCIAL OSINT & CLEARING HOUSE</span>
          </div>
          <div class="flex justify-between pt-1"><span class="text-slate-400 font-semibold uppercase">CLEARING BANK:</span> <span class="text-emerald-300 font-bold">${d.osint_clearing_bank || d.bank_institution || 'Commercial Scheduled Bank'}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-semibold uppercase">FULL ACCOUNT NO:</span> <span class="text-slate-200 font-mono">${d.account_full || node.name}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-semibold uppercase">SEC 102 CRPC FREEZE:</span> <span class="text-amber-400 font-bold">${d.osint_freeze_eligible !== false ? 'Warrant / Freezing Eligible' : 'Standard'}</span></div>
        </div>

        <!-- Account Holder & Mule Dossier -->
        <div class="p-3 bg-slate-900 border border-slate-800 rounded-lg text-xs space-y-1.5">
          <div class="flex justify-between"><span class="text-slate-400 font-bold uppercase">ACCOUNT HOLDER / MULE:</span> <span class="text-slate-200 font-bold">${d.owner || 'Mule Account Manager'}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-bold uppercase">STATUS:</span> <span class="text-red-400 font-bold">${d.custody_status || 'Frozen / Layering Identified'}</span></div>
        </div>
        ${d.notes ? `<div class="p-2.5 bg-slate-900 border border-slate-800 rounded text-[11px] text-slate-400">Context: ${d.notes}</div>` : ''}
      </div>
    `;
  } else if (node.type === "WEAPON") {
    detailsHtml = `
      <div class="space-y-3">
        <div class="p-3 bg-slate-900 border border-amber-900/60 rounded-lg text-xs space-y-1.5 shadow-inner">
          <div class="flex items-center gap-1.5 text-amber-400 font-bold text-[10px] uppercase tracking-wider border-b border-slate-800 pb-1.5">
            <i data-lucide="crosshair" class="w-3.5 h-3.5"></i>
            <span>BALLISTIC & FORENSIC PROFILE</span>
          </div>
          <div class="flex justify-between pt-1"><span class="text-slate-400 font-semibold uppercase">CALIBER / SPECIFICATION:</span> <span class="text-amber-300 font-bold">${d.caliber || node.name}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-semibold uppercase">ARMS ACT CHARGE:</span> <span class="text-red-400 font-bold">Sec 25 / 27 Arms Act</span></div>
        </div>

        <div class="p-3 bg-slate-900 border border-slate-800 rounded-lg text-xs space-y-1.5">
          <div class="flex justify-between"><span class="text-slate-400 font-bold uppercase">RECOVERED FROM:</span> <span class="text-slate-200 font-bold">${d.owner || 'Armed Operative'}</span></div>
          <div class="flex justify-between"><span class="text-slate-400 font-bold uppercase">EVIDENTIARY STATUS:</span> <span class="text-emerald-400 font-bold">${d.custody_status || 'Seized in Malkhana (Exhibit Sealed)'}</span></div>
        </div>
        ${d.notes ? `<div class="p-2.5 bg-slate-900 border border-slate-800 rounded text-[11px] text-slate-400">Context: ${d.notes}</div>` : ''}
      </div>
    `;
  } else if (node.type === "CRIME_FIR") {
    detailsHtml = `
      <div class="p-3 bg-slate-900 border border-rose-900/60 rounded-lg text-xs space-y-2">
        <div class="flex justify-between items-center border-b border-slate-800 pb-1.5">
          <span class="text-slate-400 font-bold uppercase">CASE IDENTIFIER:</span>
          <span class="text-rose-400 font-bold font-mono">${d.case_number || node.name}</span>
        </div>
        <div class="flex justify-between"><span class="text-slate-400 font-semibold uppercase">CASE STAGE:</span> <span class="text-slate-200">${d.filing_status || 'Chargesheet Filed / Under Trial'}</span></div>
        <div class="flex justify-between"><span class="text-slate-400 font-semibold uppercase">COGNIZANCE COURT:</span> <span class="text-slate-300">${d.court_cognizance || 'Chief Metropolitan Magistrate Court'}</span></div>
        <div>
          <span class="text-slate-400 block mb-1 font-bold uppercase text-[10px]">STATUTORY OFFENCES (CHARGESHEET):</span>
          <div class="flex flex-wrap gap-1">
            ${(d.statutory_offences || ["Sec 392 IPC", "Sec 120B IPC", "Sec 34 IPC"]).map(s => `<span class="px-2 py-0.5 bg-rose-950 border border-rose-800 text-rose-300 text-[10px] font-bold rounded">${s}</span>`).join('')}
          </div>
        </div>
      </div>
    `;
  } else if (node.type === "POLICE_STATION") {
    detailsHtml = `
      <div class="p-3 bg-slate-900 border border-teal-900/60 rounded-lg text-xs space-y-2">
        <div class="flex justify-between items-center border-b border-slate-800 pb-1.5">
          <span class="text-slate-400 font-bold uppercase">JURISDICTION UNIT:</span>
          <span class="text-teal-400 font-bold">${d.jurisdiction || node.name}</span>
        </div>
        <div class="flex justify-between"><span class="text-slate-400 font-semibold uppercase">INVESTIGATING OFFICER:</span> <span class="text-slate-200 font-bold">${d.investigating_officer || 'Inspector / Special Cell'}</span></div>
        <div class="flex justify-between"><span class="text-slate-400 font-semibold uppercase">INVESTIGATION STATUS:</span> <span class="text-emerald-400 font-bold">${d.fir_status || 'Active Surveillance & Warrant Execution'}</span></div>
      </div>
    `;
  }

  secBox.innerHTML = detailsHtml;
  lucide.createIcons();
}

    function updateCounters(data) {
      document.getElementById('node-count').innerText = (data.nodes || []).length;
      document.getElementById('link-count').innerText = (data.links || []).length;
      const criticalCount = (data.nodes || []).filter(n => n.type === "PERSON" && (n.risk_score >= 0.70 || n.color === '#ef4444')).length;
      document.getElementById('threat-count').innerText = criticalCount;
    }

    async function loadCurrentGraph() {
      try {
        const token = sessionStorage.getItem('ncrb_token');
        const res = await fetch(`${BACKEND_URL}/graph/data`, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        if (res.ok) {
          const data = await res.json();
          if (data.nodes && data.nodes.length > 0) {
            currentGraphData = data;
            if (GraphInstance) GraphInstance.graphData(data);
            updateCounters(data);
            renderTimeline(data);
            renderSyndicates(data);
          }
        }
      } catch (e) {
        console.warn("Backend not reached yet.");
      }
    }

    async function uploadDocument() {
      const fileInput = document.getElementById('file-input');
      const statusBox = document.getElementById('upload-status');
      const btn = document.getElementById('upload-btn');

      if (!fileInput.files[0]) return alert("Select a PDF report first.");

      btn.innerText = "RUNNING GLiNER & ML MODELS...";
      btn.disabled = true;
      statusBox.classList.remove('hidden');
      statusBox.innerText = "Extracting entities, sealing evidence & predicting roles...";

      const formData = new FormData();
      formData.append('file', fileInput.files[0]);

      try {
        const token = sessionStorage.getItem('ncrb_token');
        const res = await fetch(`${BACKEND_URL}/ingest/fir`, {
          method: 'POST',
          headers: token ? { 'Authorization': `Bearer ${token}` } : {},
          body: formData
        });

        if (!res.ok) throw new Error("Upload failed");

        const data = await res.json();
        currentGraphData = data;
        if (GraphInstance) GraphInstance.graphData(data);
        updateCounters(data);
        renderTimeline(data);
        renderSyndicates(data);
        loadEvidenceVault();

        document.getElementById('upload-modal').classList.add('hidden');
        statusBox.classList.add('hidden');
      } catch (err) {
        statusBox.innerText = "Error parsing report. Ensure backend is running.";
      } finally {
        btn.innerText = "EXTRACT & ANALYZE";
        btn.disabled = false;
      }
    }
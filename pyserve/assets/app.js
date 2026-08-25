(function(){
  const STATE = window.PYSERVE || {};
  const ROOT_NAME = STATE.rootName || 'files';
  const CAPS = STATE.caps || {};
  const LONG_PRESS_MS = 2000;
  const DASH = '-';
  const UPLOAD_CONCURRENCY = CAPS.uploadConcurrency || 3;
  const UPLOAD_AUTOCLOSE_MS = 4000;

  const ICON_FOLDER =
    '<svg width="16" height="14" viewBox="0 0 16 14" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M0.5 2.5C0.5 1.67157 1.17157 1 2 1H6L7.5 2.5H14C14.8284 2.5 15.5 3.17157 15.5 4V11.5C15.5 12.3284 14.8284 13 14 13H2C1.17157 13 0.5 12.3284 0.5 11.5V2.5Z" fill="var(--folder)" stroke="var(--folder-dark)" stroke-width="1"/></svg>';
  const ICON_FILE =
    '<svg width="13" height="16" viewBox="0 0 13 16" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M1 1.5C1 0.947715 1.44772 0.5 2 0.5H8L12 4.5V14.5C12 15.0523 11.5523 15.5 11 15.5H2C1.44772 15.5 1 15.0523 1 14.5V1.5Z" fill="#FFFFFF" stroke="var(--muted)" stroke-width="1"/>' +
    '<path d="M8 0.5V4.5H12" stroke="var(--muted)" stroke-width="1" fill="none"/></svg>';

  const ICON_COLORS = {
    code:    '#2F6FA8',
    web:     '#C4762B',
    style:   '#4B5FC7',
    data:    '#7A6BC4',
    db:      '#0F766E',
    shell:   '#3F7F3D',
    archive: '#8A6D3B',
    image:   '#2E8B57',
    video:   '#7B4BA8',
    audio:   '#B5533B',
    doc:     '#41505F',
    binary:  '#5A6270',
    disk:    '#6B7280',
    key:     '#A03D6B',
    font:    '#6D5A8A'
  };

  const FILE_TYPES = {};

  function registerTypes(kind, spec){
    const color = ICON_COLORS[kind];
    Object.keys(spec).forEach(function(label){
      spec[label].forEach(function(ext){
        FILE_TYPES[ext] = { label: label, color: color };
      });
    });
  }

  registerTypes('code', {
    'C':   ['c'],
    'H':   ['h', 'hh'],
    'C+':  ['cpp', 'cc', 'cxx', 'hpp', 'hxx', 'c++'],
    'C#':  ['cs'],
    'PY':  ['py', 'pyi', 'pyw', 'pyx'],
    'JS':  ['js', 'mjs', 'cjs'],
    'JSX': ['jsx'],
    'TS':  ['ts', 'mts', 'cts'],
    'TSX': ['tsx'],
    'GO':  ['go'],
    'RS':  ['rs'],
    'RB':  ['rb', 'erb', 'gemspec'],
    'PHP': ['php'],
    'JV':  ['java'],
    'KT':  ['kt', 'kts'],
    'SW':  ['swift'],
    'SC':  ['scala', 'sbt'],
    'LU':  ['lua'],
    'PL':  ['pl', 'pm'],
    'R':   ['r'],
    'DT':  ['dart'],
    'EX':  ['ex', 'exs'],
    'ML':  ['ml', 'mli'],
    'HS':  ['hs'],
    'CJ':  ['clj', 'cljs', 'edn'],
    'ZG':  ['zig'],
    'NM':  ['nim'],
    'V':   ['v', 'sv'],
    'AS':  ['asm', 's'],
    'NB':  ['ipynb'],
    'DK':  ['dockerfile', 'containerfile']
  });

  registerTypes('web', {
    '<>':  ['html', 'htm', 'xhtml'],
    'VUE': ['vue'],
    'SVL': ['svelte'],
    'HBS': ['hbs', 'handlebars', 'mustache'],
    'JNJ': ['jinja', 'jinja2', 'j2', 'twig']
  });

  registerTypes('style', {
    'CSS': ['css'],
    'SCS': ['scss', 'sass'],
    'LES': ['less'],
    'STY': ['styl']
  });

  registerTypes('data', {
    '{}':  ['json', 'jsonc', 'json5', 'geojson'],
    'YML': ['yaml', 'yml'],
    'TML': ['toml'],
    'XML': ['xml', 'xsd', 'xsl', 'xslt', 'rss', 'atom'],
    'CFG': ['ini', 'cfg', 'conf', 'cnf', 'properties', 'editorconfig'],
    'ENV': ['env'],
    'LCK': ['lock'],
    'IGN': ['gitignore', 'dockerignore', 'npmignore', 'eslintignore', 'ignore'],
    'PRO': ['proto'],
    'PLT': ['plist']
  });

  registerTypes('db', {
    'SQL': ['sql', 'ddl', 'dml'],
    'DB':  ['db', 'sqlite', 'sqlite3', 'mdb', 'accdb', 'dbf'],
    'CSV': ['csv'],
    'TSV': ['tsv'],
    'PQ':  ['parquet', 'orc', 'avro']
  });

  registerTypes('shell', {
    'SH':  ['sh', 'bash', 'zsh', 'ksh', 'fish', 'bashrc', 'zshrc'],
    'BAT': ['bat', 'cmd'],
    'PS1': ['ps1', 'psm1', 'psd1'],
    'MK':  ['mk', 'mak', 'makefile', 'gnumakefile'],
    'AWK': ['awk'],
    'NIX': ['nix'],
    'TF':  ['tf', 'tfvars']
  });

  registerTypes('archive', {
    'ZIP': ['zip', 'zipx'],
    'TAR': ['tar'],
    'TGZ': ['tar.gz', 'tgz', 'gz'],
    'TBZ': ['tar.bz2', 'tbz', 'tbz2', 'bz2'],
    'TXZ': ['tar.xz', 'txz', 'xz', 'lzma'],
    'ZST': ['tar.zst', 'tzst', 'zst'],
    'RAR': ['rar'],
    '7Z':  ['7z'],
    'LZ4': ['lz4'],
    'DEB': ['deb'],
    'RPM': ['rpm'],
    'JAR': ['jar', 'war', 'ear'],
    'APK': ['apk', 'aab'],
    'WHL': ['whl', 'egg'],
    'CAB': ['cab'],
    'PKG': ['pkg', 'snap', 'flatpak', 'appimage']
  });

  registerTypes('image', {
    'PNG': ['png', 'apng'],
    'JPG': ['jpg', 'jpeg', 'jpe', 'jfif'],
    'GIF': ['gif'],
    'SVG': ['svg', 'svgz'],
    'WBP': ['webp'],
    'BMP': ['bmp', 'dib'],
    'ICO': ['ico', 'icns', 'cur'],
    'TIF': ['tif', 'tiff'],
    'HEI': ['heic', 'heif'],
    'AVF': ['avif'],
    'PSD': ['psd'],
    'XCF': ['xcf'],
    'RAW': ['raw', 'cr2', 'cr3', 'nef', 'arw', 'dng', 'orf'],
    'AI':  ['ai'],
    'EPS': ['eps']
  });

  registerTypes('video', {
    'MP4': ['mp4', 'm4v'],
    'MKV': ['mkv'],
    'AVI': ['avi'],
    'MOV': ['mov', 'qt'],
    'WBM': ['webm'],
    'WMV': ['wmv'],
    'FLV': ['flv', 'f4v'],
    'MPG': ['mpg', 'mpeg', 'm2v', 'mts', 'm2ts'],
    '3GP': ['3gp', '3g2'],
    'VOB': ['vob'],
    'OGV': ['ogv']
  });

  registerTypes('audio', {
    'MP3': ['mp3'],
    'WAV': ['wav', 'wave'],
    'FLC': ['flac'],
    'OGG': ['ogg', 'oga'],
    'M4A': ['m4a'],
    'AAC': ['aac'],
    'OPU': ['opus'],
    'WMA': ['wma'],
    'MID': ['mid', 'midi'],
    'AIF': ['aiff', 'aif']
  });

  registerTypes('doc', {
    'MD':  ['md', 'markdown', 'mdx'],
    'TXT': ['txt', 'text', 'nfo'],
    'PDF': ['pdf'],
    'DOC': ['doc', 'docx', 'odt', 'pages'],
    'XLS': ['xls', 'xlsx', 'ods', 'numbers'],
    'PPT': ['ppt', 'pptx', 'odp', 'key'],
    'RTF': ['rtf'],
    'EPB': ['epub', 'mobi', 'azw', 'azw3', 'djvu'],
    'TEX': ['tex', 'bib', 'cls', 'sty'],
    'LOG': ['log'],
    'RST': ['rst', 'adoc', 'asciidoc'],
    'LIC': ['license', 'licence', 'copying', 'notice'],
    'CHG': ['changelog', 'authors', 'contributors']
  });

  registerTypes('binary', {
    'EXE': ['exe', 'com', 'scr'],
    'MSI': ['msi', 'msix'],
    'DLL': ['dll'],
    'SO':  ['so'],
    'DYL': ['dylib'],
    'O':   ['o', 'obj', 'ko'],
    'A':   ['a', 'lib'],
    'BIN': ['bin'],
    'ELF': ['elf', 'axf'],
    'WSM': ['wasm'],
    'APP': ['app'],
    'PYC': ['pyc', 'pyo', 'pyd'],
    'CLS': ['class'],
    'DMP': ['dmp', 'core'],
    'HEX': ['hex', 'srec']
  });

  registerTypes('disk', {
    'ISO': ['iso', 'cue', 'nrg'],
    'IMG': ['img'],
    'QC2': ['qcow2', 'qcow'],
    'VMD': ['vmdk'],
    'VDI': ['vdi'],
    'DMG': ['dmg'],
    'VHD': ['vhd', 'vhdx'],
    'OVA': ['ova', 'ovf'],
    'SWP': ['swap', 'swp']
  });

  registerTypes('key', {
    'KEY': ['pem', 'p12', 'pfx', 'jks', 'keystore'],
    'CRT': ['crt', 'cer', 'der', 'csr'],
    'PUB': ['pub'],
    'SIG': ['sig', 'asc', 'sha256', 'md5'],
    'GPG': ['gpg', 'pgp', 'kbx']
  });

  registerTypes('font', {
    'TTF': ['ttf', 'ttc'],
    'OTF': ['otf'],
    'WOF': ['woff', 'woff2'],
    'EOT': ['eot']
  });

  function extensionOf(name){
    const lower = String(name).toLowerCase();
    const dot = lower.lastIndexOf('.');
    if(dot < 0) return FILE_TYPES[lower] ? lower : '';
    if(dot === 0) return lower.slice(1);
    const previous = lower.lastIndexOf('.', dot - 1);
    if(previous > 0){
      const compound = lower.slice(previous + 1);
      if(FILE_TYPES[compound]) return compound;
    }
    return lower.slice(dot + 1);
  }

  function iconForFile(name){
    const type = FILE_TYPES[extensionOf(name)];
    if(!type) return ICON_FILE;
    const sizes = { 1: 7.5, 2: 6, 3: 4.8 };
    const fontSize = sizes[type.label.length] || 4.8;
    return '<svg width="13" height="16" viewBox="0 0 13 16" fill="none" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M1 1.5C1 0.947715 1.44772 0.5 2 0.5H8L12 4.5V14.5C12 15.0523 11.5523 15.5 11 15.5H2C1.44772 15.5 1 15.0523 1 14.5V1.5Z" fill="#FFFFFF" stroke="' + type.color + '" stroke-width="1"/>' +
      '<path d="M8 0.5V4.5H12" stroke="' + type.color + '" stroke-width="1" fill="none"/>' +
      '<rect x="0" y="8" width="13" height="6.4" rx="1.2" fill="' + type.color + '"/>' +
      '<text x="6.5" y="13.05" text-anchor="middle" font-family="\'IBM Plex Mono\', monospace" ' +
      'font-size="' + fontSize + '" font-weight="700" letter-spacing="-0.2" fill="#FFFFFF">' + type.label + '</text>' +
      '</svg>';
  }

  let currentPath = STATE.path || "";
  let currentEntries = [];
  let searchActive = false;
  let editMode = false;
  let draggingSrc = null;
  let sortKey = 'name';
  let sortDir = 1;

  const pathLine = document.getElementById('pathLine');
  const sessionLine = document.getElementById('sessionLine');
  const fileTable = document.getElementById('fileTable');
  const listing = document.getElementById('listing');
  const searchInput = document.getElementById('searchInput');
  const searchWrap = document.getElementById('searchWrap');
  const clearSearchBtn = document.getElementById('clearSearch');
  const uploadBtn = document.getElementById('uploadBtn');
  const uploadInput = document.getElementById('uploadInput');
  const doneBtn = document.getElementById('doneBtn');
  const dropOverlay = document.getElementById('dropOverlay');
  const dropOverlayPath = document.getElementById('dropOverlayPath');
  const modalBackdrop = document.getElementById('modalBackdrop');
  const modalBox = document.getElementById('modalBox');
  const toastContainer = document.getElementById('toastContainer');
  const uploadPanel = document.getElementById('uploadPanel');
  const uploadList = document.getElementById('uploadList');
  const uploadTitle = document.getElementById('uploadTitle');
  const uploadToggle = document.getElementById('uploadToggle');
  const uploadClose = document.getElementById('uploadClose');

  const canEditAnything = CAPS.rename || CAPS.move || CAPS.delete;
  let dirPerms = null;

  function may(action, entry){
    if(!CAPS[action]) return false;
    if(entry && entry.perms && entry.perms[action] === false) return false;
    return true;
  }

  function mayHere(action){
    if(!CAPS[action]) return false;
    if(dirPerms && dirPerms[action] === false) return false;
    return true;
  }

  if(!CAPS.upload) uploadBtn.style.display = 'none';
  if(!CAPS.search) searchWrap.style.display = 'none';

  function escapeHtml(s){
    return String(s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function renderSession(){
    if(!STATE.user){
      sessionLine.innerHTML = '';
      return;
    }
    sessionLine.innerHTML = '<span class="who">' + escapeHtml(STATE.user) + '</span>';
    if(STATE.authMode === 'form'){
      const btn = document.createElement('button');
      btn.className = 'logout';
      btn.type = 'button';
      btn.textContent = 'sign out';
      btn.addEventListener('click', async function(){
        await apiFetch('/api/logout', { method: 'POST' });
        window.location.replace('/login');
      });
      sessionLine.appendChild(btn);
    }
  }

  function showToast(message, kind){
    const el = document.createElement('div');
    el.className = 'toast' + (kind === 'info' ? ' info' : '');
    const text = document.createElement('span');
    text.className = 'toast-text';
    text.textContent = message;
    el.appendChild(text);
    const closeBtn = document.createElement('button');
    closeBtn.className = 'toast-close';
    closeBtn.type = 'button';
    closeBtn.setAttribute('aria-label', 'dismiss');
    closeBtn.textContent = '×';
    function remove(){ if(el.parentNode) el.parentNode.removeChild(el); }
    closeBtn.addEventListener('click', remove);
    el.appendChild(closeBtn);
    toastContainer.appendChild(el);
    setTimeout(remove, 5000);
  }

  async function safeJson(res){
    try { return await res.json(); } catch(e){ return null; }
  }

  function handleUnauthorized(res){
    if(!res || res.status !== 401) return false;
    if(STATE.authMode === 'form'){
      window.location.replace('/login?next=' + encodeURIComponent(window.location.pathname));
    } else {
      window.location.reload();
    }
    return true;
  }

  async function apiFetch(url, opts){
    try {
      const res = await fetch(url, opts);
      if(handleUnauthorized(res)) return null;
      return res;
    } catch(err){
      showToast('Network error: could not reach the server.');
      return null;
    }
  }

  function fmtSize(bytes){
    if(bytes === null || bytes === undefined) return DASH;
    const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    let value = bytes;
    let unitIndex = 0;
    while(value >= 1000 && unitIndex < units.length - 1){
      value = value / 1024;
      unitIndex++;
    }
    if(unitIndex === 0) return Math.round(value) + ' ' + units[0];
    return value.toFixed(1) + ' ' + units[unitIndex];
  }

  function fmtDate(unixSeconds){
    if(!unixSeconds && unixSeconds !== 0) return DASH;
    const d = new Date(unixSeconds * 1000);
    return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  }

  function joinPath(dir, name){
    return dir ? dir + '/' + name : name;
  }

  function downloadHref(path){
    return '/dl/' + path.split('/').map(encodeURIComponent).join('/');
  }

  function folderHref(path){
    if(!path) return '/';
    return '/' + path.split('/').map(encodeURIComponent).join('/') + '/';
  }

  function pathFromLocation(){
    return window.location.pathname.split('/').filter(Boolean).map(function(part){
      try { return decodeURIComponent(part); } catch(e){ return part; }
    }).join('/');
  }

  function isPlainClick(e){
    return e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
  }

  function navigate(path, options){
    options = options || {};
    currentPath = path;
    const href = folderHref(path);
    if(options.replace) history.replaceState({ path: path }, '', href);
    else history.pushState({ path: path }, '', href);
    if(searchActive) exitSearch();
    else load();
  }

  function onFolderLink(a, path){
    a.href = folderHref(path);
    a.addEventListener('click', function(e){
      if(!isPlainClick(e)) return;
      e.preventDefault();
      navigate(path);
    });
  }

  function showModal(html){
    modalBox.innerHTML = html;
    modalBackdrop.style.display = 'flex';
  }

  function hideModal(){
    modalBackdrop.style.display = 'none';
    modalBox.innerHTML = '';
  }

  function askConflict(filename){
    return new Promise(function(resolve){
      showModal(
        '<h3>File already exists</h3>' +
        '<p>&ldquo;' + escapeHtml(filename) + '&rdquo; already exists in this folder. Replace it, or keep both?</p>' +
        '<div class="modal-actions">' +
          '<button type="button" data-choice="cancel">Cancel</button>' +
          '<button type="button" data-choice="copy">Keep Both</button>' +
          '<button type="button" data-choice="replace" class="danger">Replace</button>' +
        '</div>'
      );
      modalBox.querySelectorAll('[data-choice]').forEach(function(btn){
        btn.addEventListener('click', function(){
          const choice = btn.getAttribute('data-choice');
          hideModal();
          resolve(choice);
        });
      });
    });
  }

  function confirmFolderDelete(folderName){
    return new Promise(function(resolve){
      showModal(
        '<h3>Delete folder</h3>' +
        '<p>Are you sure? Type the folder name &ldquo;' + escapeHtml(folderName) + '&rdquo; to confirm recursive deletion.</p>' +
        '<input type="text" id="deleteConfirmInput" autocomplete="off" placeholder="' + escapeHtml(folderName) + '">' +
        '<div class="modal-actions">' +
          '<button type="button" data-choice="cancel">Cancel</button>' +
          '<button type="button" data-choice="delete" class="danger" disabled>Delete</button>' +
        '</div>'
      );
      const input = document.getElementById('deleteConfirmInput');
      const deleteBtn = modalBox.querySelector('[data-choice="delete"]');
      input.addEventListener('input', function(){
        deleteBtn.disabled = input.value !== folderName;
      });
      modalBox.querySelector('[data-choice="cancel"]').addEventListener('click', function(){
        hideModal();
        resolve(false);
      });
      deleteBtn.addEventListener('click', function(){
        if(input.value === folderName){
          hideModal();
          resolve(true);
        }
      });
    });
  }

  async function apiList(path){
    const r = await apiFetch('/api/list?path=' + encodeURIComponent(path));
    if(!r) return null;
    if(!r.ok){
      showToast('Could not load this folder.');
      return null;
    }
    return r.json();
  }

  async function apiSearch(query, scope){
    const r = await apiFetch('/api/search?q=' + encodeURIComponent(query) +
                             '&path=' + encodeURIComponent(scope || ''));
    if(!r) return null;
    if(!r.ok){
      const data = await safeJson(r);
      return { error: (data && data.error) || 'Search failed.', matches: [] };
    }
    return r.json();
  }

  const uploads = { items: [], queue: [], active: 0, seq: 0, closeTimer: null };
  let conflictChain = Promise.resolve();

  function parseJson(text){
    try { return JSON.parse(text); } catch(e){ return null; }
  }

  function queueConflict(name){
    const answer = conflictChain.then(function(){ return askConflict(name); });
    conflictChain = answer.catch(function(){});
    return answer;
  }

  function xhrUpload(url, headers, file, onProgress){
    return new Promise(function(resolve){
      const xhr = new XMLHttpRequest();
      xhr.open('POST', url, true);
      Object.keys(headers).forEach(function(key){ xhr.setRequestHeader(key, headers[key]); });
      if(xhr.upload){
        xhr.upload.addEventListener('progress', function(e){
          if(e.lengthComputable) onProgress(e.loaded / e.total);
        });
      }
      xhr.addEventListener('load', function(){ resolve({ status: xhr.status, text: xhr.responseText }); });
      xhr.addEventListener('error', function(){ resolve(null); });
      xhr.addEventListener('abort', function(){ resolve(null); });
      xhr.send(file);
    });
  }

  function showUploadPanel(){
    if(uploads.closeTimer){ clearTimeout(uploads.closeTimer); uploads.closeTimer = null; }
    uploadPanel.classList.add('visible');
    uploadPanel.classList.remove('collapsed');
  }

  function hideUploadPanel(){
    uploadPanel.classList.remove('visible');
    uploads.items = [];
    uploadList.innerHTML = '';
  }

  function renderUploadItem(item){
    const row = document.createElement('div');
    row.className = 'upload-item';

    const icon = document.createElement('span');
    icon.className = 'icon-wrap';
    icon.innerHTML = iconForFile(item.name);
    row.appendChild(icon);

    const meta = document.createElement('div');
    meta.className = 'upload-meta';
    const name = document.createElement('div');
    name.className = 'upload-name';
    name.textContent = item.name;
    name.title = item.target ? item.target + '/' + item.name : item.name;
    meta.appendChild(name);
    const bar = document.createElement('div');
    bar.className = 'upload-bar';
    const fill = document.createElement('span');
    bar.appendChild(fill);
    meta.appendChild(bar);
    row.appendChild(meta);

    const state = document.createElement('span');
    state.className = 'upload-state';
    state.textContent = 'waiting';
    row.appendChild(state);

    item.el = row;
    item.fill = fill;
    item.stateEl = state;
    uploadList.appendChild(row);
  }

  function setUploadProgress(item, fraction){
    item.progress = Math.max(0, Math.min(1, fraction));
    item.fill.style.width = Math.round(item.progress * 100) + '%';
    if(item.status === 'uploading'){
      item.stateEl.textContent = Math.round(item.progress * 100) + '%';
    }
  }

  function setUploadStatus(item, status, detail){
    item.status = status;
    item.el.classList.remove('done', 'failed', 'skipped');
    if(status === 'uploading'){
      item.stateEl.textContent = Math.round(item.progress * 100) + '%';
    } else if(status === 'done'){
      item.el.classList.add('done');
      item.stateEl.textContent = fmtSize(item.size);
    } else if(status === 'failed'){
      item.el.classList.add('failed');
      item.stateEl.textContent = 'failed';
      item.stateEl.title = detail || '';
    } else if(status === 'skipped'){
      item.el.classList.add('skipped');
      item.stateEl.textContent = 'skipped';
    }
    updateUploadTitle();
  }

  function updateUploadTitle(){
    const total = uploads.items.length;
    if(!total) return;
    const done = uploads.items.filter(function(i){ return i.status === 'done'; }).length;
    const failed = uploads.items.filter(function(i){ return i.status === 'failed'; }).length;
    const skipped = uploads.items.filter(function(i){ return i.status === 'skipped'; }).length;
    const settled = done + failed + skipped;

    if(settled < total){
      uploadTitle.textContent = 'Uploading ' + (settled + 1) + ' of ' + total;
      return;
    }
    const bits = [];
    if(done) bits.push(done + ' uploaded');
    if(failed) bits.push(failed + ' failed');
    if(skipped) bits.push(skipped + ' skipped');
    uploadTitle.textContent = bits.join(', ');
    if(!failed && !skipped){
      uploads.closeTimer = setTimeout(hideUploadPanel, UPLOAD_AUTOCLOSE_MS);
    }
  }

  function applyUploadedEntry(targetPath, entry){
    if(targetPath !== currentPath || searchActive) return;
    const index = currentEntries.findIndex(function(e){
      return e.name === entry.name && e.type === entry.type;
    });
    if(index >= 0) currentEntries[index] = entry;
    else currentEntries.push(entry);
    renderListing();
    flashRow(entry.name);
  }

  function flashRow(name){
    Array.prototype.forEach.call(listing.querySelectorAll('tr[data-name]'), function(row){
      if(row.getAttribute('data-name') !== name) return;
      row.classList.remove('just-added');
      void row.offsetWidth;
      row.classList.add('just-added');
    });
  }

  async function runUpload(item, conflictChoice){
    setUploadStatus(item, 'uploading');
    const headers = {
      'X-Target-Path': encodeURIComponent(item.target),
      'X-Filename': encodeURIComponent(item.name)
    };
    if(conflictChoice) headers['X-Conflict'] = conflictChoice;

    const res = await xhrUpload('/api/upload', headers, item.file, function(fraction){
      setUploadProgress(item, fraction);
    });

    if(!res){
      setUploadStatus(item, 'failed', 'could not reach the server');
      return;
    }
    if(res.status === 401){
      setUploadStatus(item, 'failed', 'signed out');
      handleUnauthorized({ status: 401 });
      return;
    }
    if(res.status === 409){
      const data = parseJson(res.text);
      const choice = await queueConflict((data && data.name) || item.name);
      if(choice === 'cancel'){
        setUploadStatus(item, 'skipped');
        return;
      }
      setUploadProgress(item, 0);
      return runUpload(item, choice);
    }
    if(res.status < 200 || res.status >= 300){
      const data = parseJson(res.text);
      setUploadStatus(item, 'failed', (data && data.error) || ('HTTP ' + res.status));
      return;
    }

    const data = parseJson(res.text) || {};
    setUploadProgress(item, 1);
    item.size = data.size === undefined ? item.size : data.size;
    setUploadStatus(item, 'done');
    applyUploadedEntry(item.target, {
      name: data.name || item.name,
      type: 'file',
      size: item.size,
      mtime: data.mtime
    });
  }

  function pumpUploads(){
    while(uploads.active < UPLOAD_CONCURRENCY && uploads.queue.length){
      const item = uploads.queue.shift();
      uploads.active++;
      runUpload(item).then(function(){
        uploads.active--;
        pumpUploads();
      });
    }
    updateUploadTitle();
  }

  function uploadFilesInto(targetPath, fileList){
    if(!CAPS.upload){
      showToast('Uploads are disabled on this server.');
      return;
    }
    const files = Array.from(fileList || []);
    if(!files.length) return;

    if(uploads.items.length && uploads.items.every(function(i){ return i.status !== 'queued' && i.status !== 'uploading'; })){
      uploads.items = [];
      uploadList.innerHTML = '';
    }
    showUploadPanel();

    files.forEach(function(file){
      const limit = CAPS.maxUploadBytes || 0;
      const item = {
        id: ++uploads.seq,
        name: file.name,
        size: file.size,
        target: targetPath,
        status: 'queued',
        progress: 0,
        file: file
      };
      uploads.items.push(item);
      renderUploadItem(item);
      if(limit && file.size > limit){
        setUploadStatus(item, 'failed', 'larger than the maximum upload size');
        return;
      }
      uploads.queue.push(item);
    });

    pumpUploads();
  }

  uploadToggle.addEventListener('click', function(){
    uploadPanel.classList.toggle('collapsed');
    uploadToggle.innerHTML = uploadPanel.classList.contains('collapsed') ? '&plus;' : '&minus;';
  });
  uploadClose.addEventListener('click', hideUploadPanel);

  async function apiRename(path, newName){
    const res = await apiFetch('/api/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path, newName: newName })
    });
    if(!res) return false;
    if(res.status === 409){
      showToast('"' + newName + '" already exists in this folder.');
      return false;
    }
    if(!res.ok){
      const data = await safeJson(res);
      showToast('Rename failed' + ((data && data.error) ? ': ' + data.error : '.'));
      return false;
    }
    return true;
  }

  async function apiMove(path, targetDir, conflict){
    const res = await apiFetch('/api/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path, targetDir: targetDir, conflict: conflict || '' })
    });
    if(!res) return false;
    if(res.status === 409){
      const data = await safeJson(res);
      const choice = await askConflict((data && data.name) || '');
      if(choice === 'cancel') return false;
      return apiMove(path, targetDir, choice);
    }
    if(!res.ok){
      const data = await safeJson(res);
      showToast('Move failed' + ((data && data.error) ? ': ' + data.error : '.'));
      return false;
    }
    return true;
  }

  async function apiDelete(path, confirmName){
    const res = await apiFetch('/api/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: path, name: confirmName || '' })
    });
    if(!res) return false;
    if(!res.ok){
      const data = await safeJson(res);
      showToast('Delete failed' + ((data && data.error) ? ': ' + data.error : '.'));
      return false;
    }
    return true;
  }

  function renderPath(){
    const segs = currentPath ? currentPath.split('/') : [];
    const names = [ROOT_NAME].concat(segs);
    pathLine.innerHTML = '';
    names.forEach(function(name, i){
      if(i === names.length - 1){
        const current = document.createElement('span');
        current.className = 'current';
        current.textContent = name;
        pathLine.appendChild(current);
        return;
      }
      const a = document.createElement('a');
      a.textContent = name;
      onFolderLink(a, names.slice(1, i + 1).join('/'));
      pathLine.appendChild(a);
      const sep = document.createElement('span');
      sep.className = 'sep';
      sep.textContent = '/';
      pathLine.appendChild(sep);
    });
  }

  function sortEntries(entries){
    const dirs = entries.filter(function(e){ return e.type === 'dir'; });
    const files = entries.filter(function(e){ return e.type !== 'dir'; });
    function cmp(a, b){
      let av, bv;
      if(sortKey === 'name'){ av = a.name.toLowerCase(); bv = b.name.toLowerCase(); }
      else if(sortKey === 'size'){ av = a.size || 0; bv = b.size || 0; }
      else { av = a.mtime || 0; bv = b.mtime || 0; }
      if(av < bv) return -1 * sortDir;
      if(av > bv) return 1 * sortDir;
      return 0;
    }
    dirs.sort(cmp);
    files.sort(cmp);
    return dirs.concat(files);
  }

  function updateSortHeaders(){
    document.querySelectorAll('thead th').forEach(function(th){
      const key = th.getAttribute('data-sort');
      const arrow = th.querySelector('.arrow');
      if(key === sortKey){
        th.classList.add('sorted');
        arrow.textContent = sortDir === 1 ? '▲' : '▼';
      } else {
        th.classList.remove('sorted');
        arrow.textContent = '';
      }
    });
  }

  document.querySelectorAll('thead th').forEach(function(th){
    th.addEventListener('click', function(){
      const key = this.getAttribute('data-sort');
      if(sortKey === key){ sortDir *= -1; }
      else { sortKey = key; sortDir = 1; }
      load();
    });
  });

  function setEditMode(v){
    editMode = v;
    doneBtn.style.display = v ? 'inline-block' : 'none';
    load();
  }

  doneBtn.addEventListener('click', function(){ setEditMode(false); });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && editMode) setEditMode(false);
  });

  function attachLongPress(el){
    if(!canEditAnything) return;
    let timer = null;
    function start(){ timer = setTimeout(function(){ setEditMode(true); }, LONG_PRESS_MS); }
    function cancel(){ if(timer){ clearTimeout(timer); timer = null; } }
    el.addEventListener('pointerdown', start);
    el.addEventListener('pointerup', cancel);
    el.addEventListener('pointerleave', cancel);
    el.addEventListener('pointercancel', cancel);
  }

  function startRename(item, itemPath, nameCell, displayEl){
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'rename-input';
    input.value = item.name;
    nameCell.replaceChild(input, displayEl);
    input.focus();
    if(input.setSelectionRange) input.setSelectionRange(0, input.value.length);

    let settled = false;
    async function commit(){
      if(settled) return;
      settled = true;
      const newName = input.value.trim();
      if(newName && newName !== item.name){
        await apiRename(itemPath, newName);
      }
      load();
    }
    function cancel(){
      if(settled) return;
      settled = true;
      load();
    }
    input.addEventListener('keydown', function(e){
      if(e.key === 'Enter'){ e.preventDefault(); e.stopPropagation(); commit(); }
      else if(e.key === 'Escape'){ e.preventDefault(); e.stopPropagation(); cancel(); }
    });
    input.addEventListener('blur', commit);
  }

  async function handleDeleteClick(item, itemPath){
    if(item.type === 'dir'){
      const confirmed = await confirmFolderDelete(item.name);
      if(!confirmed) return;
      await apiDelete(itemPath, item.name);
    } else {
      await apiDelete(itemPath, '');
    }
    load();
  }

  function buildRow(item, itemPath, opts){
    opts = opts || {};
    const row = document.createElement('tr');
    row.setAttribute('data-name', item.name);
    const nameCell = document.createElement('td');
    nameCell.className = 'name';

    const isDir = item.type === 'dir';
    const showEditUI = opts.editable && editMode;

    if(showEditUI && may('delete', item)){
      const badge = document.createElement('span');
      badge.className = 'edit-badge';
      badge.textContent = '−';
      badge.title = isDir ? 'Delete folder' : 'Delete file';
      badge.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        handleDeleteClick(item, itemPath);
      });
      nameCell.appendChild(badge);
    }

    const iconWrap = document.createElement('span');
    iconWrap.className = 'icon-wrap' + (showEditUI ? ' wiggle' : '');
    iconWrap.innerHTML = isDir ? ICON_FOLDER : iconForFile(item.name);
    nameCell.appendChild(iconWrap);

    if(showEditUI && may('rename', item)){
      const nameSpan = document.createElement('span');
      nameSpan.className = 'name-text-editable';
      nameSpan.textContent = item.name;
      nameSpan.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        startRename(item, itemPath, nameCell, nameSpan);
      });
      nameCell.appendChild(nameSpan);
    } else if(showEditUI){
      const nameSpan = document.createElement('span');
      nameSpan.textContent = item.name;
      nameCell.appendChild(nameSpan);
    } else if(isDir){
      const a = document.createElement('a');
      a.textContent = item.name;
      onFolderLink(a, itemPath);
      nameCell.appendChild(a);
    } else if(may('download', item)){
      const a = document.createElement('a');
      a.href = downloadHref(itemPath);
      a.textContent = item.name;
      nameCell.appendChild(a);
    } else {
      const nameSpan = document.createElement('span');
      nameSpan.textContent = item.name;
      nameCell.appendChild(nameSpan);
    }

    row.appendChild(nameCell);

    const sizeCell = document.createElement('td');
    sizeCell.className = 'size';
    sizeCell.textContent = isDir ? DASH : fmtSize(item.size);
    row.appendChild(sizeCell);

    const dateCell = document.createElement('td');
    dateCell.className = 'date';
    dateCell.textContent = fmtDate(item.mtime);
    row.appendChild(dateCell);

    if(opts.editable){
      attachLongPress(row);

      if(editMode && may('move', item)){
        row.draggable = true;
        row.addEventListener('dragstart', function(e){
          draggingSrc = { path: itemPath, name: item.name, isDir: isDir };
          row.classList.add('dragging');
          if(e.dataTransfer){
            e.dataTransfer.effectAllowed = 'move';
            try { e.dataTransfer.setData('text/plain', item.name); } catch(err){}
          }
        });
        row.addEventListener('dragend', function(){
          row.classList.remove('dragging');
          draggingSrc = null;
        });
      }

      if(isDir && (may('upload', item) || CAPS.move)){
        row.addEventListener('dragover', function(e){
          if(may('upload', item) && hasFilesPayload(e)){
            e.preventDefault();
            row.classList.add('drop-target');
            return;
          }
          if(CAPS.move && draggingSrc && draggingSrc.path !== itemPath){
            e.preventDefault();
            row.classList.add('drop-target');
          }
        });
        row.addEventListener('dragleave', function(){
          row.classList.remove('drop-target');
        });
        row.addEventListener('drop', async function(e){
          row.classList.remove('drop-target');
          if(may('upload', item) && hasFilesPayload(e)){
            e.preventDefault();
            e.stopPropagation();
            uploadFilesInto(itemPath, e.dataTransfer.files);
            return;
          }
          if(CAPS.move && draggingSrc && draggingSrc.path !== itemPath){
            e.preventDefault();
            e.stopPropagation();
            const src = draggingSrc;
            draggingSrc = null;
            const ok = await apiMove(src.path, itemPath);
            if(ok !== false) load();
          }
        });
      }
    }

    return row;
  }

  async function load(){
    const data = await apiList(currentPath);
    if(!data){
      currentEntries = [];
      updateSortHeaders();
      renderPath();
      listing.innerHTML = '<tr><td class="empty" colspan="3">could not load directory</td></tr>';
      return;
    }
    currentEntries = data.entries || [];
    dirPerms = data.perms || null;
    renderListing();
  }

  function renderListing(){
    updateSortHeaders();
    renderPath();
    uploadBtn.style.display = mayHere('upload') ? '' : 'none';
    listing.innerHTML = '';

    if(currentPath){
      const segs = currentPath.split('/');
      segs.pop();
      const parentRow = document.createElement('tr');
      parentRow.className = 'parent';
      parentRow.innerHTML = '<td class="name">' + ICON_FOLDER + '</td><td class="size"></td><td class="date"></td>';
      const up = document.createElement('a');
      up.textContent = '..';
      onFolderLink(up, segs.join('/'));
      parentRow.querySelector('td.name').appendChild(up);
      listing.appendChild(parentRow);
    }

    if(!currentEntries.length){
      const row = document.createElement('tr');
      row.innerHTML = '<td class="empty" colspan="3">empty</td>';
      listing.appendChild(row);
      return;
    }

    sortEntries(currentEntries).forEach(function(item){
      listing.appendChild(buildRow(item, joinPath(currentPath, item.name), { editable: true }));
    });
  }

  let dragDepth = 0;
  function hasFilesPayload(e){
    return !!(e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).indexOf('Files') !== -1);
  }

  window.addEventListener('dragenter', function(e){
    if(!mayHere('upload') || !hasFilesPayload(e)) return;
    e.preventDefault();
    dragDepth++;
    dropOverlayPath.textContent = (currentPath ? currentPath : ROOT_NAME) + '/';
    dropOverlay.style.display = 'flex';
  });
  window.addEventListener('dragover', function(e){
    if(!mayHere('upload') || !hasFilesPayload(e)) return;
    e.preventDefault();
  });
  window.addEventListener('dragleave', function(){
    dragDepth = Math.max(0, dragDepth - 1);
    if(dragDepth === 0) dropOverlay.style.display = 'none';
  });
  window.addEventListener('drop', function(e){
    if(!mayHere('upload') || !hasFilesPayload(e)) return;
    e.preventDefault();
    dragDepth = 0;
    dropOverlay.style.display = 'none';
    if(e.dataTransfer.files && e.dataTransfer.files.length){
      uploadFilesInto(currentPath, e.dataTransfer.files);
    }
  });

  uploadBtn.addEventListener('click', function(){ uploadInput.click(); });
  uploadInput.addEventListener('change', function(){
    if(this.files && this.files.length){
      uploadFilesInto(currentPath, this.files);
    }
    this.value = '';
  });

  function scopeName(scope){
    if(!scope) return ROOT_NAME;
    const segs = scope.split('/');
    return segs[segs.length - 1];
  }

  function runSearch(query){
    const scope = currentPath;
    searchActive = true;
    fileTable.classList.add('search-mode');
    listing.innerHTML = '<tr><td class="empty" colspan="3">searching&hellip;</td></tr>';
    pathLine.innerHTML = 'results for &ldquo;' + escapeHtml(query) + '&rdquo; in ' +
      '<span class="current">' + escapeHtml(scopeName(scope)) + '</span>';

    apiSearch(query, scope).then(function(data){
      if(!data){
        listing.innerHTML = '<tr><td class="empty" colspan="3">search failed</td></tr>';
        return;
      }
      if(data.error){
        listing.innerHTML = '';
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.className = 'empty search-error';
        cell.colSpan = 3;
        cell.textContent = data.error;
        row.appendChild(cell);
        listing.appendChild(row);
        return;
      }
      listing.innerHTML = '';
      const matches = data.matches || [];
      if(!matches.length){
        listing.innerHTML = '<tr><td class="empty" colspan="3">no matches</td></tr>';
        return;
      }

      const nodeByPath = {};
      const childrenOf = {};

      function ensureFolderChain(parts){
        let acc = '';
        for(let i = 0; i < parts.length; i++){
          const parent = acc;
          acc = acc ? acc + '/' + parts[i] : parts[i];
          if(!nodeByPath[acc]){
            nodeByPath[acc] = { name: parts[i], isDir: true, size: null, mtime: null };
          }
          (childrenOf[parent] = childrenOf[parent] || new Set()).add(acc);
        }
        return acc;
      }

      matches.forEach(function(m){
        const parentPath = ensureFolderChain(m.path);
        const full = parentPath ? parentPath + '/' + m.name : m.name;
        nodeByPath[full] = {
          name: m.name, isDir: m.type === 'dir', size: m.size, mtime: m.mtime,
          canDownload: !(m.perms && m.perms.download === false)
        };
        (childrenOf[parentPath] = childrenOf[parentPath] || new Set()).add(full);
      });

      const wrapRow = document.createElement('tr');
      const wrapTd = document.createElement('td');
      wrapTd.colSpan = 3;
      const treeEl = document.createElement('div');
      treeEl.className = 'tree';

      const rootLine = document.createElement('div');
      rootLine.className = 'tree-line tree-root';
      rootLine.textContent = scopeName(scope) + '/';
      treeEl.appendChild(rootLine);

      appendTreeChildren('', '', childrenOf, nodeByPath, treeEl, scope);

      wrapTd.appendChild(treeEl);
      wrapRow.appendChild(wrapTd);
      listing.appendChild(wrapRow);
    });
  }

  function appendTreeChildren(parentPath, prefix, childrenOf, nodeByPath, container, scope){
    const childPaths = Array.from(childrenOf[parentPath] || []);
    const kids = childPaths.map(function(p){ return { path: p, node: nodeByPath[p] }; });
    kids.sort(function(a, b){
      if(a.node.isDir !== b.node.isDir) return a.node.isDir ? -1 : 1;
      return a.node.name.toLowerCase().localeCompare(b.node.name.toLowerCase());
    });

    kids.forEach(function(kid, idx){
      const isLast = idx === kids.length - 1;
      const connector = isLast ? '└── ' : '├── ';
      const node = kid.node;

      const line = document.createElement('div');
      line.className = 'tree-line';

      const prefixSpan = document.createElement('span');
      prefixSpan.className = 'tree-prefix';
      prefixSpan.textContent = prefix + connector;
      line.appendChild(prefixSpan);

      const fullPath = joinPath(scope || '', kid.path);

      if(node.isDir){
        const a = document.createElement('a');
        a.textContent = node.name + '/';
        a.className = 'tree-dir';
        onFolderLink(a, fullPath);
        line.appendChild(a);
      } else if(CAPS.download && node.canDownload !== false){
        const a = document.createElement('a');
        a.href = downloadHref(fullPath);
        a.textContent = node.name;
        line.appendChild(a);
      } else {
        const span = document.createElement('span');
        span.textContent = node.name;
        line.appendChild(span);
      }

      if(!node.isDir){
        const meta = document.createElement('span');
        meta.className = 'tree-meta';
        meta.textContent = '  ' + fmtSize(node.size) + '  ·  ' + fmtDate(node.mtime);
        line.appendChild(meta);
      }

      container.appendChild(line);

      if(node.isDir){
        const childPrefix = prefix + (isLast ? '    ' : '│   ');
        appendTreeChildren(kid.path, childPrefix, childrenOf, nodeByPath, container, scope);
      }
    });
  }

  function exitSearch(){
    searchActive = false;
    searchInput.value = '';
    searchWrap.classList.remove('active');
    fileTable.classList.remove('search-mode');
    uploadBtn.disabled = false;
    load();
  }

  searchInput.addEventListener('input', function(){
    const q = this.value.trim();
    if(q){
      if(editMode){ editMode = false; doneBtn.style.display = 'none'; }
      searchWrap.classList.add('active');
      uploadBtn.disabled = true;
      runSearch(q);
    } else {
      searchActive = false;
      searchWrap.classList.remove('active');
      uploadBtn.disabled = false;
      fileTable.classList.remove('search-mode');
      load();
    }
  });
  clearSearchBtn.addEventListener('click', exitSearch);

  window.addEventListener('popstate', function(){
    currentPath = pathFromLocation();
    if(searchActive){
      searchActive = false;
      searchInput.value = '';
      searchWrap.classList.remove('active');
      fileTable.classList.remove('search-mode');
      uploadBtn.disabled = false;
    }
    load();
  });

  renderSession();
  history.replaceState({ path: currentPath }, '', folderHref(currentPath));
  load();
})();

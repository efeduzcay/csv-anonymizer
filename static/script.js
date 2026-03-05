document.addEventListener('DOMContentLoaded', () => {
    let currentFile = null;
    let allColumns = [];
    let nameCols = [];
    let dropCols = [];

    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const browseBtn = document.getElementById('browse-btn');
    const fileInfo = document.getElementById('file-info');
    const fileNameDisplay = document.getElementById('file-name-display');
    const removeFileBtn = document.getElementById('remove-file-btn');

    const stepUpload = document.getElementById('step-upload');
    const stepOptions = document.getElementById('step-options');
    const stepSuccess = document.getElementById('step-success');

    const nameColsList = document.getElementById('name-columns-list');
    const dropColsList = document.getElementById('drop-columns-list');

    const anonymizeBtn = document.getElementById('anonymize-btn');
    const errorMsg = document.getElementById('error-message');
    const btnText = anonymizeBtn.querySelector('.btn-text');
    const spinner = anonymizeBtn.querySelector('.spinner');

    const generateMappingCb = document.getElementById('generate-mapping');
    const summaryCard = document.getElementById('summary-card');
    const resetBtn = document.getElementById('reset-btn');

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(e => {
        dropZone.addEventListener(e, ev => { ev.preventDefault(); ev.stopPropagation(); }, false);
    });

    ['dragenter', 'dragover'].forEach(e => dropZone.addEventListener(e, () => dropZone.classList.add('dragover'), false));
    ['dragleave', 'drop'].forEach(e => dropZone.addEventListener(e, () => dropZone.classList.remove('dragover'), false));

    dropZone.addEventListener('drop', e => handleFiles(e.dataTransfer.files), false);
    browseBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', function () { handleFiles(this.files); });
    removeFileBtn.addEventListener('click', resetApp);
    resetBtn.addEventListener('click', resetApp);

    function handleFiles(files) {
        if (!files.length) return;
        const file = files[0];
        if (!file.name.toLowerCase().endsWith('.csv')) {
            showError("Lütfen geçerli bir CSV dosyası yükleyin.");
            return;
        }
        currentFile = file;
        fileNameDisplay.textContent = file.name;
        dropZone.classList.add('hidden');
        fileInfo.classList.remove('hidden');
        errorMsg.classList.add('hidden');
        stepOptions.classList.remove('hidden');
        stepOptions.classList.add('active');
        fetchColumns(file);
    }

    async function fetchColumns(file) {
        const formData = new FormData();
        formData.append('file', file);
        try {
            const res = await fetch('/api/columns', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.error) throw new Error(data.error);
            allColumns = data.columns || [];
            nameCols = data.suggested_name_columns || [];
            dropCols = data.suggested_drop_columns || [];
            renderColumns();
        } catch (err) {
            showError("Sütunlar okunamadı: " + err.message);
            nameColsList.innerHTML = '';
            dropColsList.innerHTML = '';
        }
    }

    function renderColumns() {
        nameColsList.innerHTML = '';
        dropColsList.innerHTML = '';

        if (!allColumns.length) {
            nameColsList.innerHTML = '<p class="subtitle">Sütun bulunamadı.</p>';
            dropColsList.innerHTML = '<p class="subtitle">Sütun bulunamadı.</p>';
            return;
        }

        allColumns.forEach(c => {
            nameColsList.appendChild(buildCheckbox(c, nameCols.includes(c), checked => {
                nameCols = checked ? [...nameCols, c] : nameCols.filter(x => x !== c);
            }));
            dropColsList.appendChild(buildCheckbox(c, dropCols.includes(c), checked => {
                dropCols = checked ? [...dropCols, c] : dropCols.filter(x => x !== c);
            }));
        });
    }

    function buildCheckbox(label, checked, onChange) {
        const el = document.createElement('label');
        el.className = 'custom-checkbox';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.value = label;
        input.checked = checked;
        input.addEventListener('change', e => onChange(e.target.checked));
        el.innerHTML = `<span class="checkmark"></span><span class="label-text">${label}</span>`;
        el.prepend(input);
        return el;
    }

    function showError(msg) {
        errorMsg.textContent = msg;
        errorMsg.classList.remove('hidden');
    }

    anonymizeBtn.addEventListener('click', async () => {
        if (!currentFile) return;
        if (!nameCols.length) { showError("Lütfen en az bir anonimleştirilecek sütun seçin."); return; }

        errorMsg.classList.add('hidden');
        btnText.textContent = "İşleniyor...";
        spinner.classList.remove('hidden');
        anonymizeBtn.disabled = true;

        const formData = new FormData();
        formData.append('file', currentFile);
        formData.append('name_columns', JSON.stringify(nameCols));
        formData.append('drop_columns', JSON.stringify(dropCols));
        formData.append('generate_mapping', generateMappingCb.checked);

        try {
            const res = await fetch('/api/anonymize', { method: 'POST', body: formData });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ error: "Sunucu hatası." }));
                throw new Error(err.error || "Sunucu hatası.");
            }

            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = "anonymizer_results.zip";
            document.body.appendChild(a); a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            try {
                const zip = await JSZip.loadAsync(blob);
                if (zip.file("summary.json")) {
                    const text = await zip.file("summary.json").async("string");
                    showSuccess(JSON.parse(text));
                } else {
                    showSuccess(null);
                }
            } catch {
                showSuccess(null);
            }
        } catch (err) {
            showError(err.message);
        } finally {
            btnText.textContent = "Anonimleştir & ZIP İndir";
            spinner.classList.add('hidden');
            anonymizeBtn.disabled = false;
        }
    });

    function showSuccess(summary) {
        [stepUpload, stepOptions].forEach(s => { s.classList.remove('active'); s.classList.add('hidden'); });
        stepSuccess.classList.remove('hidden');
        stepSuccess.classList.add('active');

        summaryCard.innerHTML = summary ? `
            <div class="summary-item">
                <span class="summary-label">İşlenen Satır Sayısı</span>
                <span class="summary-val">${summary.total_rows}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Benzersiz Öğrenci</span>
                <span class="summary-val">${summary.unique_students}</span>
            </div>
            <div class="summary-item">
                <span class="summary-label">Silinen Sütunlar</span>
                <span class="summary-val">${summary.deleted_columns.length ? summary.deleted_columns.join(', ') : 'Yok'}</span>
            </div>` : '<p class="subtitle">Özet bilgisi alınamadı.</p>';
    }

    function resetApp() {
        currentFile = null; allColumns = []; nameCols = []; dropCols = [];
        fileInput.value = "";

        [stepSuccess, stepOptions].forEach(s => { s.classList.remove('active'); s.classList.add('hidden'); });
        stepUpload.classList.remove('hidden'); stepUpload.classList.add('active');
        dropZone.classList.remove('hidden'); fileInfo.classList.add('hidden');
        nameColsList.innerHTML = '<div class="loading-pulse">Sütunlar analiz ediliyor...</div>';
        dropColsList.innerHTML = '<div class="loading-pulse">Sütunlar analiz ediliyor...</div>';
        errorMsg.classList.add('hidden');
    }
});

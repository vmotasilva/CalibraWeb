import codecs

path = 'boards/templates/boards/board_detail.html'
with codecs.open(path, 'r', 'utf-8') as f:
    h = f.read()

# Add the 'Copiar Imagem' button next to the share button
target_btn_only_share = '''                    <div class="d-flex align-items-center gap-3">
                        <button class="btn btn-outline-info btn-sm" onclick="prompt('Copie o link abaixo para compartilhar este calendário publicamente:', '{{ public_calendar_url }}');" title="Compartilhar calendário">
                            <i class="bi bi-share"></i> Compartilhar
                        </button>'''

new_btn = '''                    <div class="d-flex align-items-center gap-3">
                        <button class="btn btn-outline-info btn-sm" onclick="prompt('Copie o link abaixo para compartilhar este calendário publicamente:', '{{ public_calendar_url }}');" title="Compartilhar calendário">
                            <i class="bi bi-share"></i> Compartilhar
                        </button>
                        <button class="btn btn-outline-success btn-sm" onclick="copyCalendarImage(this)" title="Copiar como imagem para colar">
                            <i class="bi bi-camera"></i> Copiar Imagem
                        </button>'''

if 'copyCalendarImage(this)' not in h:
    h = h.replace(target_btn_only_share, new_btn)

# Add html2canvas and the function at the end of block scripts
script_target = '''{% endblock %}'''
script_new = '''
<!-- html2canvas para copiar calendário como imagem -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js" 
integrity="sha512-BNaRQnYJYiPSqHHDb58B0yaPfCu+Wgds8Gp/gU33kqBtgNS4tSPHuGibyoeqMV/TJlQA/bWs901m1Uu+a21qg==" 
crossorigin="anonymous" referrerpolicy="no-referrer"></script>

<script>
    function copyCalendarImage(btn) {
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Copiando...';
        btn.disabled = true;

        const calendarElement = document.getElementById('calendar-view');
        
        if (!calendarElement) {
            alert('Calendário não encontrado!');
            btn.innerHTML = originalHtml;
            btn.disabled = false;
            return;
        }

        html2canvas(calendarElement, {
            scale: 2,
            useCORS: true,
            backgroundColor: '#ffffff'
        }).then(canvas => {
            canvas.toBlob(blob => {
                try {
                    const item = new ClipboardItem({ 'image/png': blob });
                    navigator.clipboard.write([item]).then(() => {
                        btn.innerHTML = '<i class="bi bi-check-lg"></i> Copiado!';
                        btn.classList.remove('btn-outline-success');
                        btn.classList.add('btn-success');
                        
                        setTimeout(() => {
                            btn.innerHTML = originalHtml;
                            btn.classList.remove('btn-success');
                            btn.classList.add('btn-outline-success');
                            btn.disabled = false;
                        }, 3000);
                    }).catch(err => {
                        console.error('Erro ao copiar imagem:', err);
                        alert('Não foi possível copiar a imagem. Verifique as permissões do navegador.');
                        btn.innerHTML = originalHtml;
                        btn.disabled = false;
                    });
                } catch (e) {
                    console.error('Erro de compatibilidade:', e);
                    alert('Seu navegador não suporta cópia direta de imagens para a área de transferência.');
                    btn.innerHTML = originalHtml;
                    btn.disabled = false;
                }
            });
        }).catch(err => {
            console.error('Erro ao gerar imagem:', err);
            alert('Erro ao gerar a imagem do calendário.');
            btn.innerHTML = originalHtml;
            btn.disabled = false;
        });
    }
</script>
{% endblock %}
'''

# Check where the block content or end of file is if {% endblock %} is tricky
if 'function copyCalendarImage(btn)' not in h:
    # replace the LAST occurence of {% endblock %}
    parts = h.rsplit('{% endblock %}', 1)
    if len(parts) == 2:
        h = parts[0] + script_new
    else:
        h = h + script_new

with codecs.open(path, 'w', 'utf-8') as f:
    f.write(h)

print("Done")

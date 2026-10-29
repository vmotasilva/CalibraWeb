/* Plano de ação das ocorrências: várias ações, cada uma com responsáveis e prazo.
 *
 *   PlanoAcao.mount(elemento, {origem: 'laboratorio', id: 12, onChange: fn})   -> plano completo da ocorrência
 *   PlanoAcao.picker(container, {name: 'responsaveis', initial: [], multiple: true}) -> seletor AJAX de usuários
 *
 * Usa as rotas /ocorrencias/api/usuarios/, /ocorrencias/api/plano/<origem>/<id>/ e /ocorrencias/api/plano/acao/.
 */
(function (global) {
    'use strict';

    var BASE = '/ocorrencias/';

    function csrf(opts) {
        if (opts && opts.csrf) return opts.csrf;
        var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        if (m) return decodeURIComponent(m[1]);
        var i = document.querySelector('input[name=csrfmiddlewaretoken]');
        return i ? i.value : '';
    }

    function h(tag, attrs) {
        var el = document.createElement(tag);
        Object.keys(attrs || {}).forEach(function (k) {
            var v = attrs[k];
            if (v === null || v === undefined || v === false) return;
            if (k === 'class') el.className = v;
            else if (k === 'text') el.textContent = v;
            else if (k.indexOf('on') === 0) el.addEventListener(k.slice(2), v);
            else el.setAttribute(k, v === true ? '' : v);
        });
        for (var i = 2; i < arguments.length; i++) {
            var c = arguments[i];
            if (c === null || c === undefined || c === false) continue;
            el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
        }
        return el;
    }

    function injetarCss() {
        if (document.getElementById('plano-acao-css')) return;
        var css = '' +
            '.pa-picker{position:relative}' +
            '.pa-coment-lista{border-left:3px solid #dee2e6;padding-left:8px;margin-bottom:6px;font-size:.85rem}' +
            '.pa-coment-item+.pa-coment-item{margin-top:6px}' +
            '.pa-picker .pa-box{display:flex;flex-wrap:wrap;gap:4px;align-items:center;border:1px solid #ced4da;border-radius:6px;padding:4px 6px;background:#fff;min-height:38px}' +
            '.pa-picker .pa-box:focus-within{border-color:#86b7fe;box-shadow:0 0 0 .2rem rgba(13,110,253,.15)}' +
            '.pa-picker input.pa-q{border:0;outline:0;flex:1 1 140px;min-width:120px;padding:2px 4px;font-size:.9rem;background:transparent}' +
            '.pa-chip{display:inline-flex;align-items:center;gap:4px;background:#e0e7ff;color:#1e3a8a;border-radius:14px;padding:2px 4px 2px 10px;font-size:.82rem}' +
            '.pa-chip button{border:0;background:transparent;color:#1e3a8a;line-height:1;padding:0 4px;font-size:1rem;cursor:pointer}' +
            '.pa-list{position:absolute;left:0;right:0;top:100%;z-index:1090;margin-top:2px;background:#fff;border:1px solid #cbd5e1;border-radius:6px;box-shadow:0 8px 20px rgba(15,23,42,.15);max-height:220px;overflow:auto;display:none}' +
            '.pa-list.aberto{display:block}' +
            '.pa-list .pa-item{padding:6px 10px;cursor:pointer;font-size:.88rem;border-bottom:1px solid #f1f5f9}' +
            '.pa-list .pa-item:hover,.pa-list .pa-item.ativo{background:#eff6ff}' +
            '.pa-list .pa-vazio{padding:8px 10px;color:#64748b;font-size:.85rem}' +
            '.pa-acao{border-left:3px solid #94a3b8;background:#f8fafc;border-radius:6px;padding:.5rem .7rem;margin-bottom:.45rem;font-size:.88rem}' +
            '.pa-acao.ABERTA{border-left-color:#2563eb;background:#eff6ff}' +
            '.pa-acao.ABERTA.vencida{border-left-color:#dc2626;background:#fef2f2}' +
            '.pa-acao.CONCLUIDA{border-left-color:#16a34a}' +
            '.pa-acao.REDIRECIONADA{border-left-color:#f59e0b}' +
            '.pa-acao.CANCELADA{opacity:.65}' +
            '.pa-form{border:1px solid #cbd5e1;border-radius:8px;background:#fff;padding:.75rem;margin-bottom:.6rem}';
        document.head.appendChild(h('style', {id: 'plano-acao-css', text: css}));
    }

    /* ------------------------------------------------------------------ seletor AJAX de usuários */
    function picker(container, opts) {
        injetarCss();
        opts = opts || {};
        var nome = opts.name || 'responsaveis';
        var multiple = opts.multiple !== false;
        var sel = (opts.initial || []).slice();
        var timer = null, resultados = [], ativo = -1, seq = 0;

        var box = h('div', {class: 'pa-box'});
        var q = h('input', {type: 'text', class: 'pa-q', autocomplete: 'off',
                            placeholder: opts.placeholder || 'Digite para buscar pessoas…'});
        var lista = h('div', {class: 'pa-list', role: 'listbox'});
        var raiz = h('div', {class: 'pa-picker'}, box, lista);
        container.replaceChildren(raiz);

        function emitir() { if (opts.onChange) opts.onChange(sel.slice()); }

        function desenhar() {
            box.replaceChildren();
            sel.forEach(function (u) {
                box.appendChild(h('span', {class: 'pa-chip'}, u.nome,
                    h('button', {type: 'button', title: 'Remover', 'aria-label': 'Remover ' + u.nome,
                                 onclick: function () { sel = sel.filter(function (x) { return x.id !== u.id; }); desenhar(); emitir(); }}, '×'),
                    h('input', {type: 'hidden', name: nome, value: u.id})));
            });
            q.placeholder = sel.length && !multiple ? '' : (opts.placeholder || 'Digite para buscar pessoas…');
            box.appendChild(q);
        }

        function fechar() { lista.classList.remove('aberto'); ativo = -1; }

        function mostrar() {
            lista.replaceChildren();
            var livres = resultados.filter(function (r) { return !sel.some(function (s) { return s.id === r.id; }); });
            if (!livres.length) {
                lista.appendChild(h('div', {class: 'pa-vazio', text: q.value.trim() ? 'Nenhuma pessoa encontrada.' : 'Digite para buscar pessoas.'}));
            }
            livres.forEach(function (r, i) {
                lista.appendChild(h('div', {class: 'pa-item' + (i === ativo ? ' ativo' : ''), role: 'option',
                                            onmousedown: function (e) { e.preventDefault(); escolher(r); }},
                                    h('strong', {text: r.nome}), r.usuario && r.usuario !== r.nome ? h('span', {class: 'text-muted ms-2', text: r.usuario}) : null));
            });
            lista._livres = livres;
            lista.classList.add('aberto');
        }

        function buscar() {
            var minha = ++seq;
            fetch(BASE + 'api/usuarios/?q=' + encodeURIComponent(q.value.trim()), {credentials: 'same-origin'})
                .then(function (r) { return r.json(); })
                .then(function (j) { if (minha !== seq) return; resultados = j.results || []; ativo = -1; mostrar(); })
                .catch(function () { lista.replaceChildren(h('div', {class: 'pa-vazio', text: 'Não foi possível buscar.'})); lista.classList.add('aberto'); });
        }

        function escolher(u) {
            if (!multiple) sel = [];
            if (!sel.some(function (x) { return x.id === u.id; })) sel.push({id: u.id, nome: u.nome});
            q.value = '';
            desenhar(); fechar(); emitir();
            q.focus();
        }

        q.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(buscar, 250); });
        q.addEventListener('focus', buscar);
        q.addEventListener('blur', function () { setTimeout(fechar, 120); });
        q.addEventListener('keydown', function (e) {
            var livres = lista._livres || [];
            if (e.key === 'ArrowDown') { e.preventDefault(); ativo = Math.min(ativo + 1, livres.length - 1); mostrar(); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); ativo = Math.max(ativo - 1, 0); mostrar(); }
            else if (e.key === 'Enter') { e.preventDefault(); var alvo = livres[ativo >= 0 ? ativo : 0]; if (alvo && lista.classList.contains('aberto')) escolher(alvo); }
            else if (e.key === 'Escape') { fechar(); }
            else if (e.key === 'Backspace' && !q.value && sel.length) { sel.pop(); desenhar(); emitir(); }
        });
        box.addEventListener('click', function () { q.focus(); });
        desenhar();

        return {
            values: function () { return sel.map(function (s) { return s.id; }); },
            items: function () { return sel.slice(); },
            set: function (itens) { sel = (itens || []).slice(); desenhar(); emitir(); },
            clear: function () { sel = []; desenhar(); emitir(); }
        };
    }

    /* ------------------------------------------------------------------ plano de ação da ocorrência */
    function hoje() {
        var d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
        return d.toISOString().slice(0, 10);
    }

    function mount(el, opts) {
        injetarCss();
        var uid = opts.origem + ':' + opts.id;
        var dados = null, formAberto = null, aviso = null, comentando = {}, rascunho = '';

        function chamar(url, corpo) {
            var init = {credentials: 'same-origin', headers: {'X-CSRFToken': csrf(opts), 'X-Requested-With': 'XMLHttpRequest'}};
            if (corpo) { init.method = 'POST'; init.body = corpo; }
            return fetch(url, init).then(function (r) { return r.json().then(function (j) { return {ok: r.ok, dados: j}; }); });
        }

        function carregar() {
            el.replaceChildren(h('div', {class: 'small text-muted', text: 'Carregando plano de ação…'}));
            chamar(BASE + 'api/plano/' + opts.origem + '/' + opts.id + '/').then(function (r) {
                if (!r.ok) { el.replaceChildren(h('div', {class: 'small text-danger', text: r.dados.erro || 'Não foi possível carregar o plano de ação.'})); return; }
                dados = r.dados; desenhar();
            }).catch(function () { el.replaceChildren(h('div', {class: 'small text-danger', text: 'Não foi possível carregar o plano de ação.'})); });
        }

        function enviar(form, acao, acaoId, pickerResp) {
            var corpo = new FormData();
            corpo.append('uid', uid); corpo.append('acao', acao);
            if (acaoId) corpo.append('acao_id', acaoId);
            corpo.append('texto', (form.querySelector('[name=texto]') || {value: ''}).value);
            var prazo = form.querySelector('[name=prazo]');
            if (prazo) corpo.append('prazo', prazo.value);
            if (pickerResp) pickerResp.values().forEach(function (id) { corpo.append('responsaveis', id); });
            var btn = form.querySelector('button[type=submit]'); if (btn) btn.disabled = true;
            chamar(BASE + 'api/plano/acao/', corpo).then(function (r) {
                if (btn) btn.disabled = false;
                if (!r.ok) { var e = form.querySelector('.pa-erro'); e.textContent = r.dados.erro || 'Não foi possível salvar.'; return; }
                dados = r.dados.plano; formAberto = null; aviso = r.dados.mensagem; desenhar();
                if (opts.onChange) opts.onChange(dados);
            }).catch(function () { if (btn) btn.disabled = false; form.querySelector('.pa-erro').textContent = 'Falha de conexão.'; });
        }

        var CONFIG = {
            nova_acao: {titulo: 'Nova ação', ok: 'Atribuir ação', texto: 'Descreva a ação a realizar', textoObrig: true, resp: true, respRot: 'Responsáveis', prazo: true},
            concluir_acao: {titulo: 'Concluir ação', ok: 'Concluir', texto: 'Resultado da ação (opcional)', textoObrig: false},
            redirecionar_acao: {titulo: 'Redirecionar ação', ok: 'Redirecionar', texto: 'Motivo do redirecionamento', textoObrig: true, resp: true, respRot: 'Novos responsáveis', prazo: true},
            cancelar_acao: {titulo: 'Cancelar ação', ok: 'Cancelar ação', texto: 'Motivo do cancelamento', textoObrig: true}
        };

        function formulario(acao, a) {
            var c = CONFIG[acao], pk = null;
            var erro = h('div', {class: 'pa-erro text-danger small mb-2'});
            var texto = h('textarea', {name: 'texto', class: 'form-control form-control-sm', rows: 3, placeholder: c.texto, required: c.textoObrig});
            if (acao === 'nova_acao' && rascunho) { texto.value = rascunho; rascunho = ''; }
            var form = h('form', {class: 'pa-form'},
                h('div', {class: 'fw-bold small mb-2', text: c.titulo + (a ? ' — ' + a.descricao.slice(0, 60) : '')}),
                h('div', {class: 'mb-2'}, texto));
            if (c.resp) {
                var cont = h('div');
                form.appendChild(h('div', {class: 'mb-2'}, h('label', {class: 'form-label small fw-bold mb-1', text: c.respRot}), cont));
                pk = picker(cont, {name: 'responsaveis'});
            }
            if (c.prazo) {
                form.appendChild(h('div', {class: 'mb-2', style: 'max-width:220px'}, h('label', {class: 'form-label small fw-bold mb-1', text: 'Prazo'}),
                    h('input', {type: 'date', name: 'prazo', class: 'form-control form-control-sm', min: hoje()})));
            }
            form.appendChild(erro);
            form.appendChild(h('div', {class: 'd-flex gap-2 justify-content-end'},
                h('button', {type: 'button', class: 'btn btn-sm btn-light', onclick: function () { formAberto = null; desenhar(); }}, 'Voltar'),
                h('button', {type: 'submit', class: 'btn btn-sm btn-primary', text: c.ok})));
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                if (c.resp && pk && !pk.values().length) { erro.textContent = 'Selecione ao menos um responsável.'; return; }
                enviar(form, acao, a ? a.id : '', pk);
            });
            return form;
        }

        function comentarios(a) {
            var caixa = h('div', {class: 'pa-coment mt-2'});
            var lista = a.comentarios || [];
            if (lista.length) {
                var corpo = h('div', {class: 'pa-coment-lista'});
                lista.forEach(function (c) {
                    corpo.appendChild(h('div', {class: 'pa-coment-item'},
                        h('span', {class: 'text-muted', text: c.quando + ' · '}), h('strong', {text: c.autor}),
                        h('div', {style: 'white-space:pre-line', text: c.texto})));
                });
                caixa.appendChild(corpo);
            }
            if (!comentando[a.id]) {
                caixa.appendChild(h('button', {type: 'button', class: 'btn btn-sm btn-link p-0',
                    onclick: function () { comentando[a.id] = true; desenhar(); }},
                    h('i', {class: 'bi bi-chat-left-text me-1'}), lista.length ? 'Comentar (' + lista.length + ')' : 'Comentar'));
                return caixa;
            }
            var erro = h('div', {class: 'pa-erro text-danger small'});
            var texto = h('textarea', {name: 'texto', class: 'form-control form-control-sm', rows: 2, required: true,
                                       placeholder: 'Escreva uma tratativa, dúvida ou resposta…'});
            var form = h('form', {class: 'mt-1'}, texto, erro,
                h('div', {class: 'd-flex gap-2 justify-content-end mt-1'},
                    h('button', {type: 'button', class: 'btn btn-sm btn-light', onclick: function () { delete comentando[a.id]; desenhar(); }}, 'Fechar'),
                    h('button', {type: 'submit', class: 'btn btn-sm btn-primary'}, 'Comentar')));
            form.addEventListener('submit', function (e) { e.preventDefault(); enviar(form, 'comentar_acao', a.id, null); });
            caixa.appendChild(form);
            return caixa;
        }

        function nomes(lista) { return lista.length ? lista.map(function (r) { return r.nome; }).join(', ') : 'Sem responsável'; }

        function cartao(a) {
            var cls = {ABERTA: 'text-bg-primary', CONCLUIDA: 'text-bg-success', REDIRECIONADA: 'text-bg-warning', CANCELADA: 'text-bg-secondary'}[a.status];
            var meta = 'Criada ' + a.criado_em + (a.criado_por ? ' por ' + a.criado_por : '') +
                (a.de ? ' · redirecionada de ' + a.de : '') + (a.para ? ' · redirecionada para ' + a.para : '');
            var fim = a.status !== 'ABERTA' && a.encerrada_em
                ? a.status_label + ' em ' + a.encerrada_em + (a.encerrada_por ? ' por ' + a.encerrada_por : '') + (a.resultado ? ': ' + a.resultado : '') : '';
            var botoes = h('div', {class: 'd-flex flex-wrap align-content-start gap-1'});
            [['concluir_acao', a.pode_concluir, 'Concluir', 'btn-outline-success', 'bi-check2'],
             ['redirecionar_acao', a.pode_redirecionar, 'Redirecionar', 'btn-outline-primary', 'bi-arrow-right-circle'],
             ['cancelar_acao', a.pode_cancelar, 'Cancelar', 'btn-outline-danger', 'bi-x-circle']].forEach(function (b) {
                if (!b[1]) return;
                botoes.appendChild(h('button', {type: 'button', class: 'btn btn-sm ' + b[3], onclick: function () { formAberto = {acao: b[0], id: a.id}; desenhar(); }},
                    h('i', {class: 'bi ' + b[4] + ' me-1'}), b[2]));
            });
            return h('div', {class: 'pa-acao ' + a.status + (a.vencida ? ' vencida' : '')},
                h('div', {class: 'd-flex flex-wrap justify-content-between gap-2'},
                    h('div', {style: 'min-width:0'},
                        h('span', {class: 'badge ' + cls, text: a.status_label}), ' ',
                        h('strong', {text: nomes(a.responsaveis)}),
                        a.prazo_fmt ? h('span', {class: a.vencida ? 'text-danger fw-bold' : 'text-muted', text: ' · prazo ' + a.prazo_fmt + (a.vencida ? ' (vencido)' : '')}) : null,
                        h('div', {style: 'white-space:pre-line', text: a.descricao}),
                        h('div', {class: 'text-muted small', text: meta}),
                        fim ? h('div', {class: 'text-muted small', text: fim}) : null),
                    botoes),
                formAberto && formAberto.id === a.id ? h('div', {class: 'mt-2'}, formulario(formAberto.acao, a)) : null,
                comentarios(a));
        }

        function desenhar() {
            var topo = h('div', {class: 'd-flex justify-content-between align-items-center mb-2'},
                h('div', {class: 'fw-bold'}, h('i', {class: 'bi bi-list-check me-1'}), 'Plano de ação ',
                    dados.acoes.length ? h('span', {class: 'fw-normal text-muted', text: '(' + dados.acoes.length + ')'}) : null),
                dados.pode_criar ? h('button', {type: 'button', class: 'btn btn-sm btn-outline-dark', onclick: function () { formAberto = {acao: 'nova_acao', id: 0}; desenhar(); }},
                    h('i', {class: 'bi bi-plus-circle me-1'}), 'Nova ação') : null);
            var filhos = [topo];
            if (aviso) { filhos.push(h('div', {class: 'alert alert-success py-1 px-2 small', text: aviso})); aviso = null; }
            if (formAberto && formAberto.acao === 'nova_acao') filhos.push(formulario('nova_acao', null));
            if (!dados.acoes.length) {
                filhos.push(h('div', {class: 'small text-muted', text: dados.pode_criar ? 'Nenhuma ação definida. Use “Nova ação” para atribuir responsáveis e um prazo.' : 'Nenhuma ação definida.'}));
            }
            dados.acoes.forEach(function (a) { filhos.push(cartao(a)); });
            el.replaceChildren.apply(el, filhos);
        }

        carregar();
        return {
            recarregar: carregar,
            novaAcao: function (texto) {  // abre o formulário de nova ação com a descrição sugerida
                if (!dados || !dados.pode_criar) return false;
                rascunho = texto || ''; formAberto = {acao: 'nova_acao', id: 0}; desenhar();
                el.scrollIntoView({behavior: 'smooth', block: 'nearest'});
                return true;
            }
        };
    }

    global.PlanoAcao = {mount: mount, picker: picker};
})(window);

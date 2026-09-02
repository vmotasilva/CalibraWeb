import React, { useState, useEffect, useMemo } from 'react';

/**
 * MetrologiaDashboard - Componente React Full-Stack para Gestão de Metrologia & Qualidade
 * 
 * Funcionalidades:
 * 1. Abas interativas: TODOS, EXTERNO, INTERNO
 * 2. KPIs dinâmicos com contadores reativos
 * 3. Tabela com badges de Atividade (Calibração/Verificação) e Local (Interno/Externo)
 * 4. Alertas de Ocorrência (RNC / Manutenção)
 * 5. Botões de ação rápida por contexto (Nova Cotação, Agendar Execução, Reportar Ocorrência)
 */
export default function MetrologiaDashboard() {
  const [activeTab, setActiveTab] = useState('todos'); // 'todos' | 'externo' | 'interno'
  const [searchQuery, setSearchQuery] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Carregar dados da API do Django REST
  useEffect(() => {
    fetch('/metrologia/api/dashboard-overview/')
      .then((res) => {
        if (!res.ok) throw new Error('Falha ao obter dados do dashboard');
        return res.json();
      })
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Filtragem dos instrumentos com base na aba ativa e na pesquisa
  const filteredInstruments = useMemo(() => {
    if (!data?.instrumentos) return [];
    
    return data.instrumentos.filter((inst) => {
      // Filtro por Aba
      if (activeTab === 'externo' && inst.is_internal) return false;
      if (activeTab === 'interno' && !inst.is_internal) return false;

      // Filtro por Busca Textual
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const tag = (inst.tag || '').toLowerCase();
        const desc = (inst.descricao || '').toLowerCase();
        const setor = (inst.setor_nome || '').toLowerCase();
        return tag.includes(q) || desc.includes(q) || setor.includes(q);
      }

      return true;
    });
  }, [data, activeTab, searchQuery]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-teal-600"></div>
        <span className="ml-3 text-slate-600 font-medium">Carregando Dashboard de Metrologia...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-700">
        <h4 className="font-bold">Erro ao carregar dados</h4>
        <p className="text-sm">{error || 'Não foi possível conectar à API.'}</p>
      </div>
    );
  }

  const { kpis } = data;

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-4 sm:p-6 lg:p-8">
      {/* HEADER */}
      <div className="bg-gradient-to-r from-slate-900 to-teal-950 rounded-2xl p-6 text-white shadow-lg flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-white/10 text-teal-200 backdrop-blur-sm mb-2">
            Gestão da Qualidade & Metrologia
          </span>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">Dashboard de Metrologia</h1>
          <p className="text-slate-300 text-sm mt-1">
            Controle do parque de instrumentos por local de execução, atividade e ocorrências.
          </p>
        </div>
        <div className="flex gap-2">
          <a
            href="/metrologia/"
            className="px-4 py-2 bg-white text-slate-900 rounded-lg text-sm font-semibold hover:bg-slate-100 transition shadow-sm"
          >
            Listagem Completa
          </a>
          <a
            href="/metrologia/solicitacoes/"
            className="px-4 py-2 bg-white/10 text-white rounded-lg text-sm font-semibold hover:bg-white/20 transition border border-white/20"
          >
            Cotações
          </a>
        </div>
      </div>

      {/* ABAS (TABS) & BUSCA */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div className="flex items-center gap-1.5 overflow-x-auto whitespace-nowrap p-1 bg-slate-100 rounded-xl border border-slate-200 shadow-inner w-full sm:w-auto -mx-1 px-1">
          <button
            onClick={() => setActiveTab('todos')}
            className={`flex items-center gap-2 px-3.5 py-1.5 text-xs sm:text-sm font-semibold rounded-lg transition flex-shrink-0 ${
              activeTab === 'todos'
                ? 'bg-teal-700 text-white shadow'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200'
            }`}
          >
            <span>TODOS</span>
            <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-black/15 font-mono">
              {kpis.todos?.total_instrumentos || 0}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('externo')}
            className={`flex items-center gap-2 px-3.5 py-1.5 text-xs sm:text-sm font-semibold rounded-lg transition flex-shrink-0 ${
              activeTab === 'externo'
                ? 'bg-teal-700 text-white shadow'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200'
            }`}
          >
            <span>EXTERNO</span>
            <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-black/15 font-mono">
              {kpis.externo?.necessitam_cotacao || 0}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('interno')}
            className={`flex items-center gap-2 px-3.5 py-1.5 text-xs sm:text-sm font-semibold rounded-lg transition flex-shrink-0 ${
              activeTab === 'interno'
                ? 'bg-teal-700 text-white shadow'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200'
            }`}
          >
            <span>INTERNO</span>
            <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-black/15 font-mono">
              {kpis.interno?.fila_laboratorio || 0}
            </span>
          </button>
        </div>

        <div className="w-full sm:w-72">
          <input
            type="text"
            placeholder="Buscar TAG, descrição, setor..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-4 py-2 text-xs sm:text-sm bg-white border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-teal-500 shadow-sm"
          />
        </div>
      </div>

      {/* KPIS DINÂMICOS CONFORME A ABA SELECIONADA (GRID 2x2 NO MOBILE, 4 COLS EM TELAS MÉDIAS/GRANDES) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 sm:gap-4">
        {activeTab === 'todos' && (
          <>
            <div className="bg-gradient-to-br from-red-500 to-red-600 text-white p-3 sm:p-5 rounded-xl sm:rounded-2xl shadow-md flex flex-col justify-between">
              <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider opacity-90">Vencidos</span>
              <div className="text-2xl sm:text-3xl font-extrabold mt-1 sm:mt-2">{kpis.todos?.vencidos || 0}</div>
              <p className="text-[10px] sm:text-xs text-red-100 mt-0.5 sm:mt-1 truncate">Calibração imediata</p>
            </div>

            <div className="bg-gradient-to-br from-amber-500 to-amber-600 text-white p-3 sm:p-5 rounded-xl sm:rounded-2xl shadow-md flex flex-col justify-between">
              <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider opacity-90">Vencem 30D</span>
              <div className="text-2xl sm:text-3xl font-extrabold mt-1 sm:mt-2">{kpis.todos?.avencer_30 || 0}</div>
              <p className="text-[10px] sm:text-xs text-amber-100 mt-0.5 sm:mt-1 truncate">Janela de atenção</p>
            </div>

            <div className="bg-gradient-to-br from-purple-600 to-purple-700 text-white p-3 sm:p-5 rounded-xl sm:rounded-2xl shadow-md flex flex-col justify-between">
              <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider opacity-90">Ocorrências</span>
              <div className="text-2xl sm:text-3xl font-extrabold mt-1 sm:mt-2">{kpis.todos?.ocorrencias_ativas || 0}</div>
              <p className="text-[10px] sm:text-xs text-purple-100 mt-0.5 sm:mt-1 truncate">RNCs / Manutenção</p>
            </div>

            <div className="bg-gradient-to-br from-slate-700 to-slate-800 text-white p-3 sm:p-5 rounded-xl sm:rounded-2xl shadow-md flex flex-col justify-between">
              <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider opacity-90">Parque Total</span>
              <div className="text-2xl sm:text-3xl font-extrabold mt-1 sm:mt-2">{kpis.todos?.total_instrumentos || 0}</div>
              <p className="text-[10px] sm:text-xs text-slate-300 mt-0.5 sm:mt-1 truncate">{kpis.todos?.em_dia || 0} em dia</p>
            </div>
          </>
        )}

        {activeTab === 'externo' && (
          <>
            <div className="bg-gradient-to-br from-sky-500 to-sky-600 text-white p-3 sm:p-5 rounded-xl sm:rounded-2xl shadow-md flex flex-col justify-between">
              <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider opacity-90">Cotações Abertas</span>
              <div className="text-2xl sm:text-3xl font-extrabold mt-1 sm:mt-2">{kpis.externo?.cotacoes_abertas || 0}</div>
              <p className="text-[10px] sm:text-xs text-sky-100 mt-0.5 sm:mt-1 truncate">Processos em andamento</p>
            </div>

            <div className="bg-gradient-to-br from-amber-500 to-amber-600 text-white p-3 sm:p-5 rounded-xl sm:rounded-2xl shadow-md flex flex-col justify-between">
              <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider opacity-90">No Fornecedor</span>
              <div className="text-2xl sm:text-3xl font-extrabold mt-1 sm:mt-2">{kpis.externo?.orcamentos_pendentes || 0}</div>
              <p className="text-[10px] sm:text-xs text-amber-100 mt-0.5 sm:mt-1 truncate">Tratativa externa</p>
            </div>

            <div className="bg-gradient-to-br from-red-500 to-red-600 text-white p-3 sm:p-5 rounded-xl sm:rounded-2xl shadow-md flex flex-col justify-between">
              <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider opacity-90">Necessitam Cotação</span>
              <div className="text-2xl sm:text-3xl font-extrabold mt-1 sm:mt-2">{kpis.externo?.necessitam_cotacao || 0}</div>
              <p className="text-[10px] sm:text-xs text-red-100 mt-0.5 sm:mt-1 truncate">Abertura pendente</p>
            </div>
          </>
        )}

        {activeTab === 'interno' && (
          <>
            <div className="bg-gradient-to-br from-emerald-500 to-emerald-600 text-white p-3 sm:p-5 rounded-xl sm:rounded-2xl shadow-md flex flex-col justify-between">
              <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider opacity-90">Fila Lab Interno</span>
              <div className="text-2xl sm:text-3xl font-extrabold mt-1 sm:mt-2">{kpis.interno?.fila_laboratorio || 0}</div>
              <p className="text-[10px] sm:text-xs text-emerald-100 mt-0.5 sm:mt-1 truncate">Calibração prioritária</p>
            </div>

            <div className="bg-gradient-to-br from-red-500 to-red-600 text-white p-3 sm:p-5 rounded-xl sm:rounded-2xl shadow-md flex flex-col justify-between">
              <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider opacity-90">Internos Vencidos</span>
              <div className="text-2xl sm:text-3xl font-extrabold mt-1 sm:mt-2">{kpis.interno?.vencidos || 0}</div>
              <p className="text-[10px] sm:text-xs text-red-100 mt-0.5 sm:mt-1 truncate">Aguardando execução</p>
            </div>

            <div className="bg-gradient-to-br from-purple-600 to-purple-700 text-white p-3 sm:p-5 rounded-xl sm:rounded-2xl shadow-md flex flex-col justify-between">
              <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider opacity-90">Ocorrências Internas</span>
              <div className="text-2xl sm:text-3xl font-extrabold mt-1 sm:mt-2">{kpis.interno?.ocorrencias_ativas || 0}</div>
              <p className="text-[10px] sm:text-xs text-purple-100 mt-0.5 sm:mt-1 truncate">Ajustes ou avarias</p>
            </div>
          </>
        )}
      </div>

      {/* TABELA DE INSTRUMENTOS RESPONSIVA */}
      <div className="bg-white border border-slate-200 rounded-xl sm:rounded-2xl shadow-sm overflow-hidden">
        <div className="px-4 sm:px-6 py-3 sm:py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
          <div className="flex items-center gap-2">
            <h2 className="text-sm sm:text-base font-bold text-slate-800">Parque de Instrumentos</h2>
            <span className="px-2.5 py-0.5 text-xs font-semibold bg-slate-200 text-slate-700 rounded-full">
              {filteredInstruments.length} itens
            </span>
          </div>
        </div>

        <div className="overflow-x-auto w-full">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-[10px] sm:text-[11px] font-bold text-slate-500 uppercase tracking-wider font-mono">
                <th className="py-2.5 sm:py-3 px-3 sm:px-4">TAG / Código</th>
                <th className="py-2.5 sm:py-3 px-3 sm:px-4 hidden md:table-cell">Descrição</th>
                <th className="py-2.5 sm:py-3 px-3 sm:px-4 hidden lg:table-cell">Setor</th>
                <th className="py-2.5 sm:py-3 px-3 sm:px-4 text-center hidden md:table-cell">Atividade & Local</th>
                <th className="py-2.5 sm:py-3 px-3 sm:px-4">Vencimento</th>
                <th className="py-2.5 sm:py-3 px-3 sm:px-4 text-center">Status / RNC</th>
                <th className="py-2.5 sm:py-3 px-3 sm:px-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs sm:text-sm">
              {filteredInstruments.map((inst) => {
                const isVencido = inst.status_situacao === 'VENCIDO';
                const isAVencer = inst.status_situacao === 'AVENCER_30';

                return (
                  <tr key={inst.id} className="hover:bg-slate-50/80 transition-colors">
                    {/* TAG + Detalhe resumido no Mobile */}
                    <td className="py-2.5 sm:py-3 px-3 sm:px-4 font-mono font-bold text-teal-700">
                      <a href={inst.url_detalhes} className="hover:underline block">
                        {inst.tag}
                      </a>
                      <span className="text-[10px] text-slate-400 font-sans block md:hidden truncate max-w-[120px]">
                        {inst.descricao}
                      </span>
                    </td>

                    {/* DESCRIÇÃO (Oculto no mobile, visível em telas médias/grandes) */}
                    <td className="py-2.5 sm:py-3 px-3 sm:px-4 hidden md:table-cell">
                      <div className="font-semibold text-slate-800">{inst.descricao}</div>
                      <div className="text-xs text-slate-400">{inst.categoria_nome}</div>
                    </td>

                    {/* SETOR (Oculto no mobile, visível em telas grandes) */}
                    <td className="py-2.5 sm:py-3 px-3 sm:px-4 text-slate-600 text-xs hidden lg:table-cell">
                      {inst.setor_nome}
                    </td>

                    {/* ATIVIDADE & LOCAL (Oculto no mobile, visível em telas médias/grandes) */}
                    <td className="py-2.5 sm:py-3 px-3 sm:px-4 text-center hidden md:table-cell">
                      <div className="inline-flex flex-col items-center gap-1">
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            inst.activity_type === 'VERIFICACAO'
                              ? 'bg-purple-100 text-purple-800 border border-purple-200'
                              : 'bg-indigo-100 text-indigo-800 border border-indigo-200'
                          }`}
                        >
                          {inst.activity_type === 'VERIFICACAO' ? 'Verificação' : 'Calibração'}
                        </span>

                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            inst.is_internal
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-sky-50 text-sky-700 border border-sky-200'
                          }`}
                        >
                          {inst.is_internal ? 'Interno' : 'Externo'}
                        </span>
                      </div>
                    </td>

                    {/* VENCIMENTO */}
                    <td className="py-2.5 sm:py-3 px-3 sm:px-4 whitespace-nowrap">
                      <div className={`font-semibold ${isVencido ? 'text-red-600' : isAVencer ? 'text-amber-600' : 'text-slate-700'}`}>
                        {inst.data_proxima_calibracao_display}
                      </div>
                      {inst.dias_para_vencer !== null && (
                        <div className="text-[10px] sm:text-[11px] text-slate-400">
                          {isVencido ? `${Math.abs(inst.dias_para_vencer)}d atraso` : isAVencer ? `Em ${inst.dias_para_vencer}d` : 'No prazo'}
                        </div>
                      )}
                    </td>

                    {/* STATUS / RNC */}
                    <td className="py-2.5 sm:py-3 px-3 sm:px-4 text-center whitespace-nowrap">
                      <div className="flex items-center justify-center gap-1.5">
                        <span
                          className={`text-[10px] sm:text-xs font-bold px-2 sm:px-2.5 py-0.5 rounded-full ${
                            isVencido
                              ? 'bg-red-100 text-red-700 border border-red-200'
                              : isAVencer
                              ? 'bg-amber-100 text-amber-800 border border-amber-200'
                              : 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                          }`}
                        >
                          {isVencido ? 'VENCIDO' : isAVencer ? 'A VENCER' : 'EM DIA'}
                        </span>

                        {inst.has_active_occurrence && (
                          <span
                            title="Ocorrência Ativa / RNC em aberto"
                            className="inline-flex items-center justify-center w-4 h-4 sm:w-5 sm:h-5 bg-red-100 text-red-600 border border-red-300 rounded-full text-[10px] font-bold animate-pulse"
                          >
                            !
                          </span>
                        )}
                      </div>
                    </td>

                    {/* AÇÕES RÁPIDAS */}
                    <td className="py-2.5 sm:py-3 px-3 sm:px-4 text-right whitespace-nowrap">
                      <div className="inline-flex items-center gap-1.5">
                        {!inst.is_internal ? (
                          <a
                            href={`/metrologia/solicitacoes/nova/?instrumento_id=${inst.id}`}
                            className="px-2 py-1 text-[11px] sm:text-xs font-semibold bg-sky-50 text-sky-700 hover:bg-sky-100 border border-sky-200 rounded-lg transition"
                          >
                            Cotar
                          </a>
                        ) : (
                          <a
                            href={`/metrologia/?search=${inst.tag}`}
                            className="px-2 py-1 text-[11px] sm:text-xs font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 rounded-lg transition"
                          >
                            Agendar
                          </a>
                        )}

                        <a
                          href={inst.url_detalhes}
                          className="px-2 py-1 text-[11px] sm:text-xs font-medium text-slate-500 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
                          title="Ver Detalhes"
                        >
                          &rarr;
                        </a>
                      </div>
                    </td>
                  </tr>
                );
              })}

              {filteredInstruments.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    Nenhum instrumento encontrado para a seleção atual.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

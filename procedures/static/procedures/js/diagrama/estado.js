/* Editor de Diagramas (DOC.071) - módulo "estado"
 * Estado global do editor (seleção, arrasto, zoom e modo) e normalização da topologia.
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em diagrama_editor.html).
 */

/* Editor de Diagramas / Fluxogramas (DOC.071)
 * Depende das constantes definidas no template: VERSAO_ID, VERSAO_REVISAO, IS_APPROVED, CSRF_TOKEN,
 * versaoAtualizadoEm e topologia (script inline em diagrama_editor.html).
 */
if (!topologia.nodes) topologia.nodes = [];
if (!topologia.edges) topologia.edges = [];
if (!topologia.grid_data) topologia.grid_data = [];
if (!topologia.estilo_linha) topologia.estilo_linha = 'ortogonal'; // Padrão 90° para fluxogramas e organogramas
if (!topologia.schema_version) topologia.schema_version = 2;          // v2: layout_modo, conexões com kind, blocos recolhíveis
if (!topologia.layout_modo) topologia.layout_modo = 'raias';          // raias | organograma | logico | arvore

let autoSaveTimer = null;
let selectedEdgeId = null; // Conexão selecionada no canvas
let isDragging = false;
let activeNode = null;
let selectedNodeId = null;
let selectedNodeIds = new Set(); // Para multi-seleção e alinhamento
let dragOffset = { x: 0, y: 0 };
let modoAtual = 'canvas';

// Variáveis de Navegação e Zoom
let zoomLevel = 1.0;
let isPanning = false;
let panStart = { x: 0, y: 0, scrollLeft: 0, scrollTop: 0 };
let isSpacePressed = false;

// Arrasto em modos em árvore (limiar de movimento, alvo de soltura) e dimensão dinâmica do canvas
let arrastoMoveu = false;
let arrastoInicio = { x: 0, y: 0 };
let ultimoAlvoDrop = null;
let arvoreCache = null; // hierarquia calculada uma vez por renderização
let contextoEstiloCache = {};  // profundidade e ramo de cada bloco (para temas)
let efetivoCache = null;        // pessoas e vagas por ramo (quando o efetivo está visível)
let arvoreEfetivo = null;
let formatoCopiado = null;      // formato copiado ("Copiar formato")
let canvasLargura = 5000;
let canvasAltura = 5000;

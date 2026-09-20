/*
  Os dois graficos da tela de Patrimonio. Chart.js 4 (nucleo, sem plugin).

  - "Evolucao do patrimonio": uma marca por foto, com a serie nominal e, se a
    caixa do IPCA estiver ligada, a corrigida em destaque.
  - "Tendencia e projecao": grade MENSAL continua, com a serie observada e a
    curva exponencial ajustada, esta estendida por cinco anos.

  Aqui nao se soma, nao se ajusta e nao se escreve texto: o servidor manda os
  valores ja arredondados a centavos, os rotulos e os nomes das series - o
  ajuste exponencial e o R² sao calculados em `Decimal`, no servico. Este
  arquivo desenha.

  O que e comum aos graficos do projeto - cor por variavel CSS, moeda do
  tooltip, rotulo do eixo, base de opcoes e a linha - mora no `graficos.js`.
  Nenhum hexadecimal aqui.

  --- por que ele redesenha ---

  Gravar e excluir foto sao HTMX: a resposta troca o bloco `#resumo-patrimonio`
  inteiro por swap fora de banda, e os dois cartoes vem dentro dele. Depois do
  swap cada <canvas> e OUTRO elemento, com outro JSON ao lado - e as instancias
  antigas continuam vivas, penduradas em canvas que ja sairam do DOM. Por isso
  o redesenho DESTROI as anteriores antes de criar as novas, e por isso as
  referencias ficam guardadas aqui: `Chart.getChart` so acha instancia pelo
  canvas que ainda existe, e o que precisa morrer e justamente o que perdeu o
  seu.

  O gatilho e o `htmx:afterSettle`: `afterSwap` dispara antes de o DOM
  assentar, e sem filtro qualquer troca da tela mandaria redesenhar.
*/
(function () {
  'use strict';

  var BLOCO = 'resumo-patrimonio';
  var EVOLUCAO = 'grafico-patrimonio';
  var TENDENCIA = 'grafico-tendencia';

  // As instancias vivas, por id de canvas. Guardadas aqui porque depois de um
  // swap o canvas delas nao esta mais no documento e nao ha como reencontra-las.
  var vivos = {};

  function opcoesDaTela() {
    var opcoes = Graficos.opcoes();

    /*
      O eixo X destes dois graficos nao e como o das outras telas: la sao doze
      meses ou quatro anos, aqui a serie SO CRESCE - 44 fotos em setembro de
      2026, mais sessenta meses de projecao no segundo, e o acervo vai para
      tras ate 2012.

      Com todas as datas escritas, o Chart.js as girava a 50 graus e elas
      comiam mais altura que o desenho. `maxRotation: 0` proibe o giro, e ai o
      proprio autoSkip mostra so quantas couberem deitadas; `maxTicksLimit` poe
      um teto para o eixo nao virar uma regua numa tela larga. A data exata de
      cada ponto continua no tooltip.
    */
    opcoes.scales.x.ticks = { maxRotation: 0, autoSkip: true, maxTicksLimit: 12 };
    return opcoes;
  }

  function lerJson(id) {
    var fonte = document.getElementById(id);
    return fonte ? JSON.parse(fonte.textContent) : null;
  }

  function desenhaEvolucao() {
    var dados = lerJson('dados-patrimonio');
    if (!dados || !document.getElementById(EVOLUCAO)) return null;

    var g = Graficos;
    var opcoes = opcoesDaTela();
    // Uma serie so nao precisa de legenda: o titulo do cartao ja diz o que e.
    opcoes.plugins.legend.display = !!dados.corrigir;

    /*
      `tension: 0`, ao contrario da Visao Anual. As fotos sao mensais, mas o
      intervalo entre elas e irregular - quem esquece um mes tem um salto de
      dois -, e uma curva suave inventaria uma forma entre dois pontos que o
      dado nao tem. Reta entre pontos nao inventa nada.

      Com a caixa ligada, a nominal fica esmaecida e a corrigida em destaque:
      a distancia entre as duas e a inflacao, e o olho tem de cair na real. E
      a mesma leitura das Analises. Esmaecer e configuracao do Chart.js - o
      canvas nao tem folha de estilo.
    */
    var datasets = [];
    dados.series.forEach(function (serie, i) {
      var corrigida = i === 1;
      // A serie corrigida SO entra quando a caixa esta ligada. O JSON traz as
      // duas sempre - e o servidor que decide o que se ve, nao o JavaScript,
      // mas quem respeita a marca ao redesenhar e este bloco.
      if (corrigida && !dados.corrigir) return;

      var esmaecida = !corrigida && dados.corrigir;
      var extra = { tension: 0 };
      if (esmaecida) {
        extra.borderWidth = 1.5;
        extra.borderDash = [4, 4];
        extra.pointRadius = 0;
      }
      datasets.push(g.linha(
        serie, g.cor(esmaecida ? '--grafico-total' : '--grafico-saldo'), extra));
    });

    return g.desenhar(EVOLUCAO, {
      type: 'line',
      data: { labels: dados.rotulos, datasets: datasets },
      options: opcoes
    });
  }

  function desenhaTendencia() {
    var dados = lerJson('dados-tendencia');
    if (!dados || !document.getElementById(TENDENCIA)) return null;

    var g = Graficos;
    var opcoes = opcoesDaTela();

    /*
      Sem marcadores nas duas: sao mais de cem pontos mensais, e um disco em
      cada um viraria uma faixa cheia. O que se le aqui e a FORMA das linhas.

      `spanGaps` na serie observada: mes sem foto e "nao medi", e nao "valia
      zero" - ligar os vizinhos e o desenho honesto. E o contrario da regra
      das Analises, onde o buraco e um mes em que nao se gastou e a linha
      precisa encostar no eixo. Os sessenta meses do futuro sao `null` e ficam
      sem linha nenhuma, que e o ponto.
    */
    var serie = g.linha(dados.serie, g.cor('--grafico-saldo'), {
      tension: 0, pointRadius: 0, pointHoverRadius: 4,
      borderWidth: 2.5, spanGaps: true
    });

    // A tendencia pontilhada, noutra cor: ela atravessa tambem o PASSADO, que
    // e onde se ve o quanto adere, e so depois segue pelos cinco anos.
    var tendencia = g.linha(dados.tendencia, g.cor('--grafico-nao-essencial'), {
      tension: 0, pointRadius: 0, pointHoverRadius: 4,
      borderWidth: 1.5, borderDash: [3, 3]
    });

    return g.desenhar(TENDENCIA, {
      type: 'line',
      data: { labels: dados.rotulos, datasets: [serie, tendencia] },
      options: opcoes
    });
  }

  function desenhar() {
    if (typeof Chart === 'undefined' || typeof Graficos === 'undefined') return;

    Object.keys(vivos).forEach(function (id) {
      if (vivos[id]) vivos[id].destroy();
      delete vivos[id];
    });

    Graficos.padroes();

    [[EVOLUCAO, desenhaEvolucao], [TENDENCIA, desenhaTendencia]]
      .forEach(function (par) {
        var canvas = document.getElementById(par[0]);
        // Cinto alem do suspensorio: se por algum caminho sobrou instancia
        // NESTE canvas, ela sai antes - o Chart.js recusa criar duas no mesmo.
        if (canvas) {
          var presa = Chart.getChart(canvas);
          if (presa) presa.destroy();
        }
        var instancia = par[1]();
        if (instancia) vivos[par[0]] = instancia;
      });
  }

  desenhar();

  document.body.addEventListener('htmx:afterSettle', function (e) {
    var alvo = e.target;
    if (!alvo || !alvo.querySelector) return;
    // O bloco pode SER o alvo assentado ou conte-lo. Um swap que nao traz os
    // cartoes tambem conta: e o que acontece quando a ultima foto e excluida e
    // os graficos deixam de existir - as instancias precisam morrer junto.
    if (alvo.id === BLOCO || alvo.querySelector('#' + BLOCO)) desenhar();
  });
})();

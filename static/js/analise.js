/*
  O grafico da Analise por subcategoria. Chart.js 4 (nucleo, sem plugin).

  Aqui nao se soma, nao se corrige e nao se escreve texto: o servidor manda os
  pontos ja arredondados a centavos, os rotulos de cada ponto e os nomes das
  series (inclusive "A precos de agosto de 2026"). Este arquivo desenha.

  O que e comum a este grafico e aos da Visao Anual - cor por variavel CSS,
  moeda do tooltip, rotulo do eixo, base de opcoes e a linha - mora no
  `graficos.js`.

  Zero e zero: a serie traz 0, nunca null, e nao ha `spanGaps`. Mes sem
  lancamento e a linha encostando no eixo, que e a informacao; buraco
  interpolado seria uma reta por cima de um mes em que nao se gastou nada.
*/
(function () {
  'use strict';

  var fonte = document.getElementById('dados-analise');
  if (!fonte || typeof Chart === 'undefined' || typeof Graficos === 'undefined') {
    return;
  }

  var dados = JSON.parse(fonte.textContent);
  var g = Graficos;
  g.padroes();

  var opcoes = g.opcoes();

  // Uma serie so nao precisa de legenda: o titulo da pagina ja diz o que e.
  opcoes.plugins.legend.display = dados.series.length > 1;

  // O tooltip ganha duas coisas que a Anual nao tem: quantos lancamentos
  // formaram aquele ponto (e o que separa "comprei mais vezes" de "comprei
  // mais caro") e o aviso de ponto parcial.
  opcoes.plugins.tooltip.callbacks.afterBody = function (itens) {
    if (!itens.length) return '';
    var i = itens[0].dataIndex;
    var quantidade = dados.quantidades[i];
    var linhas = [quantidade === 1 ? '1 lançamento'
                                   : quantidade + ' lançamentos'];
    if (dados.parciais[i]) linhas.push('período parcial');
    return linhas;
  };

  // Com correcao, a nominal fica esmaecida e a corrigida em destaque: a
  // distancia entre as duas e a inflacao, e o olho tem de cair na real.
  // Esmaecer e configuracao do Chart.js (cor e espessura do traco), nao CSS -
  // o canvas nao tem folha de estilo.
  var comCorrecao = dados.series.length > 1;

  // `tension: 0` desfaz a suavizacao da Anual. La as series sao continuas e a
  // curva ajuda a ler a tendencia; aqui um mes sem lancamento e ZERO, e uma
  // curva suave passaria por baixo do zero no caminho ate ele - desenhando um
  // gasto negativo que nao existe. Reta entre pontos nao inventa nada.
  var datasets = dados.series.map(function (serie, i) {
    // A serie 0 e sempre a nominal; a 1, quando existe, e a corrigida.
    var esmaecida = comCorrecao && i === 0;
    var extra = { tension: 0 };
    if (esmaecida) {
      extra.borderWidth = 1.5;
      extra.borderDash = [4, 4];
      extra.pointRadius = 0;
    }
    return g.linha(serie,
                   g.cor(esmaecida ? '--grafico-total' : '--grafico-despesa'),
                   extra);
  });

  g.desenhar('grafico-analise', {
    type: 'line',
    data: { labels: dados.rotulos, datasets: datasets },
    options: opcoes
  });
})();

/*
  A curva do modelo na tela de Independencia financeira. Chart.js 4 (nucleo,
  sem plugin). Quarta tela do sistema a desenhar.

  Aqui nao se calcula nada e nao se escreve texto: o servidor manda cada ponto
  com o rotulo do tooltip pronto ("2024: 57,7% -> 14,7 anos"), os nomes das
  tres series e os titulos dos dois eixos. Este arquivo desenha.

  O que e comum aos graficos do projeto - cor por variavel CSS, base de
  opcoes, a linha - mora no `graficos.js`. Nenhum hexadecimal aqui.

  Duas coisas da base NAO servem a esta tela, e as duas sao trocadas abaixo: o
  eixo Y e o tooltip da base falam em REAIS, e aqui o Y sao ANOS. Partir da
  base e mexer no que devolve e o caminho previsto pelo proprio `graficos.js`,
  e e o que a Visao Anual ja fazia no grafico do acumulado.
*/
(function () {
  'use strict';

  var fonte = document.getElementById('dados-independencia');
  if (!fonte || typeof Chart === 'undefined' || typeof Graficos === 'undefined') {
    return;
  }

  var dados = JSON.parse(fonte.textContent);
  var g = Graficos;
  g.padroes();

  var opcoes = g.opcoes();

  /*
    O eixo X e NUMERICO (taxa de poupanca em %), e nao uma lista de rotulos:
    a curva tem 91 pontos e os anos do acervo caem em taxas quebradas
    (57,7 %), que precisam pousar no lugar exato da curva - com escala de
    categoria eles cairiam no degrau mais proximo e o ponto mentiria sobre
    onde o ano esta.
  */
  opcoes.scales.x = {
    type: 'linear',
    min: dados.eixo.min,
    max: dados.eixo.max,
    title: { display: true, text: dados.titulo_x, color: g.cor('--grafico-rotulo') },
    grid: { display: false },
    border: { display: false }
  };

  // O Y da base formata reais; aqui sao anos, entao o `callback` sai e fica o
  // numero puro que o Chart.js ja escolhe para a escala.
  opcoes.scales.y = {
    beginAtZero: true,
    title: { display: true, text: dados.titulo_y, color: g.cor('--grafico-rotulo') },
    border: { display: false },
    grid: { color: g.cor('--grafico-grade') },
    ticks: { maxTicksLimit: 6 }
  };

  /*
    `index` agrupa pelo indice do ponto, que so faz sentido quando as series
    compartilham os mesmos rotulos - nao e o caso aqui, onde a curva tem 91
    pontos e os anos, quatro. `nearest` com `intersect` responde pelo ponto
    sob o ponteiro, que e o que a tela quer dizer.
  */
  opcoes.interaction = { mode: 'nearest', intersect: true };

  // O rotulo inteiro vem do servidor. O espaco da frente afasta o texto do
  // quadradinho de cor, como na base.
  opcoes.plugins.tooltip.callbacks.label = function (ctx) {
    return ' ' + ctx.raw.rotulo;
  };

  var datasets = [
    // A curva: linha continua, sem marcador. `tension: 0` porque a curva do
    // modelo e uma funcao suave amostrada de 1 em 1 ponto percentual - a
    // suavizacao do Chart.js nao acrescentaria nada e inventaria curvatura
    // entre pontos que ja estao densos.
    g.linha({ rotulo: dados.curva.nome, valores: dados.curva.pontos },
            g.cor('--grafico-total'),
            { tension: 0, pointRadius: 0, pointHoverRadius: 0, borderWidth: 2 })
  ];

  // Os anos do acervo: pontos, sem linha. `showLine: false` e o que impede o
  // Chart.js de ligar 2023 a 2026 com um traco que nao significa nada - a
  // ordem deles no eixo e por TAXA, nao por tempo.
  datasets.push(g.linha({ rotulo: dados.anos.nome, valores: dados.anos.pontos },
                        g.cor('--grafico-saldo'),
                        { showLine: false, pointRadius: 5, pointHoverRadius: 7 }));

  if (dados.meta) {
    datasets.push(g.linha({ rotulo: dados.meta.nome, valores: dados.meta.pontos },
                          g.cor('--grafico-nao-essencial'),
                          { showLine: false, pointRadius: 6, pointHoverRadius: 8,
                            pointStyle: 'rectRot' }));
  }

  g.desenhar('grafico-independencia', {
    type: 'line',
    data: { datasets: datasets },
    options: opcoes
  });
})();

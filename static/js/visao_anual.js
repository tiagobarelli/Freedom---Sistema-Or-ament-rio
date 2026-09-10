/*
  Graficos da Visao Anual. Chart.js 4 (nucleo, sem plugin), arquivo local.

  Divisao de trabalho: o servidor manda os numeros ja somados - inclusive o
  saldo acumulado - dentro de <script type="application/json">. Aqui nao se
  soma, nao se calcula media e nao se acumula nada: so desenha e formata.

  As cores tambem nao moram aqui. Sao variaveis CSS (--grafico-*, secao 1 do
  app.css) lidas por getComputedStyle, para o tema continuar tendo um dono so:
  a folha de estilo. Nenhum hexadecimal neste arquivo - nem o do tooltip, nem o
  do miolo do ponto das linhas, que no prototipo do handoff eram literais.

  As opcoes (legenda embaixo com ponto, tooltip escuro em BRL, eixo sem borda,
  raio de barra, tensao das linhas, area preenchida, empilhamento) sao as da
  funcao build() do prototipo.
*/
(function () {
  'use strict';

  var fonte = document.getElementById('dados-graficos');
  // A tela pode existir sem o JSON e o Chart.js pode nao ter carregado: nos
  // dois casos, sair calado e melhor que quebrar o resto da pagina.
  if (!fonte || typeof Chart === 'undefined') return;

  var dados = JSON.parse(fonte.textContent);
  var raiz = getComputedStyle(document.documentElement);

  function cor(nome) {
    return raiz.getPropertyValue(nome).trim();
  }

  // pt-BR: R$ 1.234,56 no tooltip. No eixo o formato e outro (ver `naEscala`).
  var moeda = new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL'
  });
  var moedaCurta = new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', maximumFractionDigits: 0
  });

  Chart.defaults.font.family = cor('--font') || Chart.defaults.font.family;
  Chart.defaults.font.size = 11;
  Chart.defaults.color = cor('--grafico-rotulo');

  // Rotulo do eixo Y. O desenho pede "R$ 140 mil": com centavos o rotulo fica
  // longo e o Chart.js passa a esconder marcacoes. Mas "mil" so serve quando a
  // escala chega la - num ano de poucos lancamentos, R$ 200 viraria "R$ 0 mil".
  // Por isso a decisao olha a maior marcacao da escala, e nao a marcacao atual:
  // o eixo inteiro sai numa unidade so.
  function naEscala(valor, _indice, marcas) {
    if (valor === 0) return '0';
    var maior = 0;
    for (var i = 0; i < marcas.length; i++) {
      maior = Math.max(maior, Math.abs(marcas[i].value));
    }
    if (maior < 1000) return moedaCurta.format(valor);
    return (valor < 0 ? '-R$ ' : 'R$ ') +
           Math.round(Math.abs(valor) / 1000) + ' mil';
  }

  // --- base comum dos quatro ------------------------------------------------
  // maintainAspectRatio:false + altura fixa no CSS (.grafico__area): sem a
  // altura no pai, o canvas cresce a cada redimensionamento.
  function opcoes(empilhado) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            usePointStyle: true,
            pointStyle: 'circle',
            boxWidth: 6,
            boxHeight: 6,
            padding: 18
          }
        },
        tooltip: {
          backgroundColor: cor('--grafico-tooltip'),
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            // O espaco da frente afasta o texto do quadradinho de cor.
            label: function (ctx) {
              return ' ' + ctx.dataset.label + ': ' + moeda.format(ctx.parsed.y);
            }
          }
        }
      },
      scales: {
        x: {
          stacked: !!empilhado,
          grid: { display: false },
          border: { display: false }
        },
        y: {
          stacked: !!empilhado,
          beginAtZero: true,
          border: { display: false },
          grid: { color: cor('--grafico-grade') },
          ticks: { maxTicksLimit: 5, callback: naEscala }
        }
      }
    };
  }

  function desenhar(id, config) {
    var canvas = document.getElementById(id);
    if (canvas) new Chart(canvas.getContext('2d'), config);
  }

  // --- 1. Receitas x Despesas: barras agrupadas -----------------------------
  function barra(serie, corSerie, raio) {
    return {
      label: serie.rotulo,
      data: serie.valores,
      backgroundColor: corSerie,
      borderRadius: raio,
      borderSkipped: raio ? false : 'start',
      barPercentage: 0.75,
      categoryPercentage: 0.62
    };
  }

  var rd = dados.receitas_despesas;
  desenhar('grafico-receitas-despesas', {
    type: 'bar',
    data: {
      labels: dados.meses,
      datasets: [
        barra(rd[0], cor('--grafico-receita'), 6),
        barra(rd[1], cor('--grafico-despesa'), 6)
      ]
    },
    options: opcoes()
  });

  // --- 2. Essenciais x Nao essenciais: linhas, Total tracejado --------------
  function linha(serie, corSerie, extra) {
    return Object.assign({
      label: serie.rotulo,
      data: serie.valores,
      borderColor: corSerie,
      backgroundColor: corSerie,
      borderWidth: 2,
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 5,
      // Miolo claro no ponto: o marcador fica anelado, e nao um disco cheio.
      pointBackgroundColor: cor('--surface'),
      pointBorderWidth: 2,
      fill: false
    }, extra || {});
  }

  var ess = dados.essencialidade;
  desenhar('grafico-essencialidade', {
    type: 'line',
    data: {
      labels: dados.meses,
      datasets: [
        linha(ess[0], cor('--grafico-essencial')),
        linha(ess[1], cor('--grafico-nao-essencial')),
        // O total nao e uma terceira categoria, e a soma das outras duas:
        // traco fino e tracejado, sem ponto, para nao ser lido como irmao.
        linha(ess[2], cor('--grafico-total'),
              { borderWidth: 1.5, borderDash: [4, 4], pointRadius: 0 })
      ]
    },
    options: opcoes()
  });

  // --- 3. Poupanca acumulada: area preenchida e linha do zero --------------
  // beginAtZero mantem o zero dentro da escala mesmo num ano inteiro no azul
  // (ou inteiro no vermelho); a area preenche ate a origem, entao o trecho
  // negativo aparece desenhado para baixo, sem colorir ponto a ponto.
  //
  // O realce da linha do zero nao esta no prototipo, e fica: com os dados dele
  // (nove meses no azul) a linha nunca aparece, mas num ano que atravesse o
  // zero ela e o que separa ter sobrado de ter faltado.
  var acumulado = dados.acumulado[0];
  var opcoesAcumulado = opcoes();
  opcoesAcumulado.plugins.legend.display = false;
  opcoesAcumulado.scales.y.grid = {
    color: function (ctx) {
      return ctx.tick.value === 0 ? cor('--grafico-zero') : cor('--grafico-grade');
    },
    lineWidth: function (ctx) {
      return ctx.tick.value === 0 ? 1.5 : 1;
    }
  };

  desenhar('grafico-acumulado', {
    type: 'line',
    data: {
      labels: dados.meses,
      datasets: [linha(acumulado, cor('--grafico-saldo'), {
        fill: 'origin',
        backgroundColor: cor('--grafico-saldo-area')
      })]
    },
    options: opcoesAcumulado
  });

  // --- 4. Nao essenciais por prioridade: barras empilhadas -----------------
  // A ordem das series e a que o servidor mandou (P1..P4 e, se houver, Sem
  // prioridade); a rampa de cor acompanha essa ordem. Sem raio: numa pilha, o
  // canto arredondado abriria um vao entre as faixas.
  var coresPrioridade = ['--grafico-p1', '--grafico-p2', '--grafico-p3',
                         '--grafico-p4', '--grafico-sem-prioridade'];

  desenhar('grafico-prioridades', {
    type: 'bar',
    data: {
      labels: dados.meses,
      datasets: dados.prioridades.map(function (serie, i) {
        return barra(serie, cor(coresPrioridade[i]), 0);
      })
    },
    options: opcoes(true)
  });
})();

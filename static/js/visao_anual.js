/*
  Graficos da Visao Anual. Chart.js 4 (nucleo, sem plugin).

  Divisao de trabalho: o servidor manda os numeros ja somados - inclusive o
  saldo acumulado - dentro de <script type="application/json">. Aqui nao se
  soma, nao se calcula media e nao se acumula nada: so desenha e formata.

  As cores tambem nao moram aqui. Sao variaveis CSS (--grafico-*, secao 1 do
  app.css) lidas por getComputedStyle, para o tema continuar tendo um dono so:
  a folha de estilo.
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

  // pt-BR: R$ 1.234,56 no tooltip. No eixo, o mesmo formato sem centavos -
  // com eles o rotulo fica longo e o Chart.js passa a esconder marcacoes.
  var moeda = new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL'
  });
  var moedaCurta = new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', maximumFractionDigits: 0
  });

  Chart.defaults.font.family = cor('--fonte') || Chart.defaults.font.family;
  Chart.defaults.font.size = 12;
  Chart.defaults.color = cor('--cor-texto-suave');

  // --- base comum dos quatro ------------------------------------------------
  // maintainAspectRatio:false + altura fixa no CSS (.grafico__area): sem a
  // altura no pai, o canvas cresce a cada redimensionamento.
  function opcoes() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'bottom',
          labels: { usePointStyle: true, boxWidth: 8, padding: 14 }
        },
        tooltip: {
          callbacks: {
            label: function (ctx) {
              return ctx.dataset.label + ': ' + moeda.format(ctx.parsed.y);
            }
          }
        }
      },
      scales: {
        x: {
          stacked: false,
          grid: { display: false },
          ticks: { color: cor('--cor-texto-fraco') }
        },
        y: {
          stacked: false,
          beginAtZero: true,
          border: { display: false },
          grid: { color: cor('--grafico-grade') },
          ticks: {
            color: cor('--cor-texto-fraco'),
            callback: function (valor) { return moedaCurta.format(valor); }
          }
        }
      }
    };
  }

  function desenhar(id, config) {
    var canvas = document.getElementById(id);
    if (canvas) new Chart(canvas.getContext('2d'), config);
  }

  // --- 1. Receitas x Despesas: barras agrupadas -----------------------------
  var rd = dados.receitas_despesas;
  desenhar('grafico-receitas-despesas', {
    type: 'bar',
    data: {
      labels: dados.meses,
      datasets: [
        {
          label: rd[0].rotulo,
          data: rd[0].valores,
          backgroundColor: cor('--grafico-receita'),
          borderRadius: 3
        },
        {
          label: rd[1].rotulo,
          data: rd[1].valores,
          backgroundColor: cor('--grafico-despesa'),
          borderRadius: 3
        }
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
      pointRadius: 2.5,
      pointHoverRadius: 5,
      tension: 0.25,
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
        // traco mais grosso e tracejado para nao ser lido como irmao delas.
        linha(ess[2], cor('--grafico-total'),
              { borderWidth: 3, borderDash: [6, 4], pointRadius: 0 })
      ]
    },
    options: opcoes()
  });

  // --- 3. Poupanca acumulada: area preenchida e linha do zero --------------
  // beginAtZero mantem o zero dentro da escala mesmo num ano inteiro no azul
  // (ou inteiro no vermelho); a area preenche ate a origem, entao o trecho
  // negativo aparece desenhado para baixo, sem colorir ponto a ponto.
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
      datasets: [{
        label: acumulado.rotulo,
        data: acumulado.valores,
        borderColor: cor('--grafico-saldo'),
        backgroundColor: cor('--grafico-saldo-area'),
        borderWidth: 2.5,
        pointRadius: 3,
        pointHoverRadius: 6,
        tension: 0.25,
        fill: 'origin'
      }]
    },
    options: opcoesAcumulado
  });

  // --- 4. Nao essenciais por prioridade: barras empilhadas -----------------
  // A ordem das series e a que o servidor mandou (P1..P4 e, se houver, Sem
  // prioridade); a rampa de cor acompanha essa ordem.
  var coresPrioridade = ['--grafico-p1', '--grafico-p2', '--grafico-p3',
                         '--grafico-p4', '--grafico-sem-prioridade'];
  var opcoesPilha = opcoes();
  opcoesPilha.scales.x.stacked = true;
  opcoesPilha.scales.y.stacked = true;

  desenhar('grafico-prioridades', {
    type: 'bar',
    data: {
      labels: dados.meses,
      datasets: dados.prioridades.map(function (serie, i) {
        return {
          label: serie.rotulo,
          data: serie.valores,
          backgroundColor: cor(coresPrioridade[i]),
          borderRadius: 2
        };
      })
    },
    options: opcoesPilha
  });
})();

/*
  O que toda tela com Chart.js deste projeto faz igual.

  Nasceu na rodada 24, quando a Analise por subcategoria virou a segunda tela a
  desenhar: cor lida de variavel CSS, moeda pt-BR no tooltip, eixo Y sem
  centavos e a base de opcoes eram para ser copiadas do `visao_anual.js` - e
  helper duplicado, neste projeto, e contradicao. A Anual continua com o que e
  so dela (barras, pilha de prioridades, area do acumulado); aqui fica o que as
  duas repetiriam.

  Nenhum hexadecimal neste arquivo. As cores sao variaveis CSS (--grafico-*,
  secao 1 do app.css) lidas por getComputedStyle, para o tema continuar tendo
  um dono so: a folha de estilo.

  Sem efeito colateral na carga: quem chama `padroes()` e cada tela, depois de
  conferir que o Chart.js esta la.
*/
var Graficos = (function () {
  'use strict';

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

  // Rotulo do eixo Y. O desenho pede "R$ 140 mil": com centavos o rotulo fica
  // longo e o Chart.js passa a esconder marcacoes. Mas "mil" so serve quando o
  // PASSO entre as marcacoes chega la - com marcacoes de 500 em 500, arredondar
  // para milhar escreve "R$ 2 mil" duas vezes seguidas (visto na Analise por
  // subcategoria, rodada 24, onde um mes de combustivel e R$ 1.300).
  // A decisao olha o eixo inteiro, e nao a marcacao atual: o eixo sai numa
  // unidade so.
  function naEscala(valor, _indice, marcas) {
    if (valor === 0) return '0';
    var passo = Infinity;
    for (var i = 1; i < marcas.length; i++) {
      passo = Math.min(passo, Math.abs(marcas[i].value - marcas[i - 1].value));
    }
    if (!(passo >= 1000)) return moedaCurta.format(valor);
    return (valor < 0 ? '-R$ ' : 'R$ ') +
           Math.round(Math.abs(valor) / 1000) + ' mil';
  }

  function padroes() {
    if (typeof Chart === 'undefined') return;
    Chart.defaults.font.family = cor('--font') || Chart.defaults.font.family;
    Chart.defaults.font.size = 11;
    Chart.defaults.color = cor('--grafico-rotulo');
  }

  // --- base comum ----------------------------------------------------------
  // maintainAspectRatio:false + altura fixa no CSS (.grafico__area): sem a
  // altura no pai, o canvas cresce a cada redimensionamento.
  //
  // Quem precisa de outra coisa parte daqui e mexe no objeto devolvido - e o
  // que a propria Anual ja fazia com o grafico do acumulado.
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

  function desenhar(id, config) {
    var canvas = document.getElementById(id);
    if (canvas) return new Chart(canvas.getContext('2d'), config);
    return null;
  }

  return {
    cor: cor,
    moeda: moeda,
    moedaCurta: moedaCurta,
    naEscala: naEscala,
    padroes: padroes,
    opcoes: opcoes,
    linha: linha,
    desenhar: desenhar
  };
})();

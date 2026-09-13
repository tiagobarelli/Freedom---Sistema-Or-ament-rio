/*
  Graficos da Visao Anual. Chart.js 4 (nucleo, sem plugin), arquivo local.

  Divisao de trabalho: o servidor manda os numeros ja somados - inclusive o
  saldo acumulado - dentro de <script type="application/json">. Aqui nao se
  soma, nao se calcula media e nao se acumula nada: so desenha e formata.

  O que esta tela faz igual a Analise por subcategoria mora no `graficos.js`
  desde a rodada 24: cor por variavel CSS, moeda do tooltip, rotulo do eixo,
  base de opcoes, a linha e o `desenhar`. Aqui fica o que e so daqui - as
  barras, a pilha das prioridades e a area do acumulado.

  As opcoes (legenda embaixo com ponto, tooltip escuro em BRL, eixo sem borda,
  raio de barra, tensao das linhas, area preenchida, empilhamento) sao as da
  funcao build() do prototipo.
*/
(function () {
  'use strict';

  var fonte = document.getElementById('dados-graficos');
  // A tela pode existir sem o JSON e o Chart.js (ou o graficos.js) pode nao ter
  // carregado: nos tres casos, sair calado e melhor que quebrar o resto da
  // pagina.
  if (!fonte || typeof Chart === 'undefined' || typeof Graficos === 'undefined') {
    return;
  }

  var dados = JSON.parse(fonte.textContent);
  var g = Graficos;
  var cor = g.cor;
  var opcoes = g.opcoes;

  g.padroes();

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
  g.desenhar('grafico-receitas-despesas', {
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
  var ess = dados.essencialidade;
  g.desenhar('grafico-essencialidade', {
    type: 'line',
    data: {
      labels: dados.meses,
      datasets: [
        g.linha(ess[0], cor('--grafico-essencial')),
        g.linha(ess[1], cor('--grafico-nao-essencial')),
        // O total nao e uma terceira categoria, e a soma das outras duas:
        // traco fino e tracejado, sem ponto, para nao ser lido como irmao.
        g.linha(ess[2], cor('--grafico-total'),
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

  g.desenhar('grafico-acumulado', {
    type: 'line',
    data: {
      labels: dados.meses,
      datasets: [g.linha(acumulado, cor('--grafico-saldo'), {
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

  g.desenhar('grafico-prioridades', {
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

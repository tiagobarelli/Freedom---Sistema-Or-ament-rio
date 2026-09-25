/*
  O "i" da observacao (rodada 36): o botao ao lado da descricao, nas quatro
  tabelas que listam lancamento - recentes, consulta, receitas e o detalhe da
  Visao Mensal. O HTML sai da macro `observacao` do `_macros.html`.

  O balao e um popover do HTML, apontado pelo `popovertarget` do botao. O
  navegador ja faz a parte dificil: camada de cima (nenhuma `.tabela-caixa`
  recorta), Esc, clique fora e o nome acessivel da relacao. Sem este arquivo
  o balao continua abrindo no clique, so que no meio da tela.

  O que este arquivo acrescenta sao duas coisas:

  - ABRIR AO PASSAR O MOUSE, e fechar quando o mouse sai do botao. So para
    `pointerType === 'mouse'`: no toque o `pointerover` tambem dispara, e
    abrir ali brigaria com o clique que vem logo em seguida. Clicar num balao
    que o mouse abriu o FIXA em vez de fecha-lo - senao quem passa o mouse e
    clica, que e o gesto de quem quer ler com calma, veria o balao sumir.
    Fixado, fecha como qualquer popover: outro clique, Esc ou clique fora.

  - FICAR COLADO AO BOTAO. Por isso o clique e sempre tratado aqui (o
    `preventDefault` cancela a acao do `popovertarget`): abrindo pelo script,
    a posicao e calculada ANTES da primeira pintura, e o balao nao pisca no
    meio da tela. Por que nao o `anchor-name` do CSS: no celular o balao e
    mais largo que a sobra dos dois lados do icone, e nenhum lado do
    `position-try` cabe - ali o certo e encostar na margem da janela, que e
    a conta de tres linhas do `posicionar`.

  Por delegacao no documento, porque as linhas chegam depois: a despesa
  recem-gravada, a pagina seguinte da consulta, o detalhe da Mensal.

  A posicao e `fixed` (e a do popover), e por isso rolar ou redimensionar
  recalcula: a linha anda, e o balao anda com ela.
*/
(function () {
  'use strict';

  // Navegador sem popover: o atributo e ignorado e o texto aparece solto na
  // celula. Legivel, e nada aqui ajudaria.
  if (!('popover' in HTMLElement.prototype)) return;

  var VAO = 6;        // px entre o botao e o balao
  var MARGEM = 16;    // px ate a borda da janela: a calha do celular

  // O balao que o mouse abriu e que o mouse ainda pode fechar ao sair.
  var peloMouse = null;

  function botaoDo(alvo) {
    return alvo && alvo.closest ? alvo.closest('.observacao__botao') : null;
  }

  function balaoDo(botao) {
    return document.getElementById(botao.getAttribute('popovertarget'));
  }

  function aberto(balao) {
    return balao.matches(':popover-open');
  }

  // Embaixo do botao, com a borda esquerda na do icone; empurrado para dentro
  // se passar da margem direita, e para cima do botao se nao couber embaixo.
  function posicionar(botao, balao) {
    var s = balao.style;
    s.inset = 'auto';
    s.margin = '0';
    s.left = '0px';
    s.top = '0px';
    var caixa = balao.getBoundingClientRect();
    var alvo = botao.getBoundingClientRect();
    var largura = document.documentElement.clientWidth;
    var altura = document.documentElement.clientHeight;

    var esquerda = Math.max(MARGEM,
      Math.min(alvo.left, largura - caixa.width - MARGEM));
    var topo = alvo.bottom + VAO;
    if (topo + caixa.height > altura - MARGEM &&
        alvo.top - VAO - caixa.height >= MARGEM) {
      topo = alvo.top - VAO - caixa.height;
    }
    s.left = esquerda + 'px';
    s.top = topo + 'px';
  }

  function abrir(botao, balao) {
    // `source` faz do botao o dono do balao para o navegador (foco e leitor
    // de tela); quem nao conhece a opcao a ignora.
    if (!aberto(balao)) balao.showPopover({ source: botao });
    posicionar(botao, balao);
  }

  function fechar(balao) {
    if (aberto(balao)) balao.hidePopover();
  }

  document.addEventListener('pointerover', function (e) {
    if (e.pointerType !== 'mouse') return;
    var botao = botaoDo(e.target);
    // Andar do <svg> para o <button> tambem e `pointerover`: so conta entrar.
    if (!botao || botao.contains(e.relatedTarget)) return;
    var balao = balaoDo(botao);
    if (!balao || aberto(balao)) return;
    abrir(botao, balao);
    peloMouse = balao;
  });

  document.addEventListener('pointerout', function (e) {
    if (e.pointerType !== 'mouse') return;
    var botao = botaoDo(e.target);
    if (!botao || botao.contains(e.relatedTarget)) return;
    var balao = balaoDo(botao);
    if (balao && balao === peloMouse) {
      peloMouse = null;
      fechar(balao);
    }
  });

  // Enter e Espaco no botao tambem chegam aqui como `click`.
  document.addEventListener('click', function (e) {
    var botao = botaoDo(e.target);
    if (!botao) return;
    var balao = balaoDo(botao);
    if (!balao) return;
    e.preventDefault();
    if (!aberto(balao)) {
      peloMouse = null;
      abrir(botao, balao);
    } else if (balao === peloMouse) {
      peloMouse = null;               // aberto pelo mouse: o clique fixa
    } else {
      fechar(balao);
    }
  });

  // Rolar ou redimensionar move o botao, e o balao vai junto. Fechar na
  // rolagem foi a primeira ideia e piscava: o `scroll` chega um quadro depois
  // do `pointerover`, e todo "i" que passava debaixo do ponteiro abria e
  // fechava em seguida.
  function reposicionar() {
    document.querySelectorAll('.observacao__balao').forEach(function (balao) {
      if (!aberto(balao)) return;
      var botao = document.querySelector('[popovertarget="' + balao.id + '"]');
      if (botao) posicionar(botao, balao);
    });
  }

  // Captura: `scroll` nao borbulha, e a `.tabela-caixa` rola por conta propria.
  window.addEventListener('scroll', reposicionar, { capture: true, passive: true });
  window.addEventListener('resize', reposicionar);
})();

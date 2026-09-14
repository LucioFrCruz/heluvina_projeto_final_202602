/*
 * Mapa coroplético dos 5.570 municípios — módulo compartilhado.
 *
 * Usado em dois lugares, com a mesma malha e os mesmos dados:
 *   - docs/mapa.html        (página standalone, com header, legenda e botões)
 *   - docs/apresentacao.html (slide do deck, inicializado preguiçosamente no
 *     evento slidechanged do reveal)
 *
 * Uso:
 *   inicializarMapa({
 *     container:    '#mapa-slide',     // obrigatório: onde o SVG é desenhado
 *     tooltip:      '#tooltip',        // opcional: se ausente, cria um próprio
 *     status:       '#status',         // opcional: linha de status de carga
 *     legend:       '#legend',         // opcional: se ausente, não renderiza legenda
 *     botoesCamada: [btnEl, ...],      // opcional: alterna IPB V3 / Arquétipos
 *     botaoReset:   '#reset-zoom'      // opcional: recentraliza com transição
 *   });
 *
 * Retorna uma Promise que resolve quando o mapa está desenhado.
 */
(function (global) {
  'use strict';

  var CORES_ARQUETIPOS = {
    'Perfil intermediario - empresarial': '#4e79a7',
    'Perfil intermediario - tradicional': '#f28e2b',
    'Sem rede bancaria - renda alta': '#59a14f',
    'Sem rede bancaria - renda baixa': '#e15759',
    'Turismo - com rede': '#b07aa1',
    'Turismo - sem banco': '#76b7b2'
  };
  var COR_SEM_DADO = '#d7dbe0';
  var LARGURA = 1000;
  var ALTURA = 920;

  function resolverElemento(alvo) {
    if (!alvo) { return null; }
    if (typeof alvo === 'string') { return document.querySelector(alvo); }
    return alvo;
  }

  function criarTooltipProprio() {
    var tooltip = document.createElement('div');
    tooltip.setAttribute('aria-hidden', 'true');
    tooltip.style.cssText =
      'position:absolute;display:none;pointer-events:none;' +
      'background:rgba(31,41,55,.94);color:#f8fafc;font-size:12px;line-height:1.5;' +
      'padding:8px 10px;border-radius:8px;max-width:260px;z-index:10;' +
      'box-shadow:0 4px 14px rgba(0,0,0,.25);';
    document.body.appendChild(tooltip);
    return tooltip;
  }

  function fmtNumero(v) {
    if (v === null || v === undefined) { return '—'; }
    return Number(v).toLocaleString('pt-BR', { maximumFractionDigits: 2 });
  }

  function buscarJson(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) { throw new Error(url + ' respondeu HTTP ' + r.status); }
      return r.json();
    });
  }

  function inicializarMapa(opcoes) {
    var container = resolverElemento(opcoes.container);
    if (!container) { return Promise.reject(new Error('container do mapa não encontrado')); }

    var tooltip = resolverElemento(opcoes.tooltip) || criarTooltipProprio();
    var statusEl = resolverElemento(opcoes.status);
    var legendEl = resolverElemento(opcoes.legend);
    var botoesCamada = opcoes.botoesCamada || [];
    var botaoReset = resolverElemento(opcoes.botaoReset);
    var camadaAtual = 'ipb';
    var corIpb = null;

    function corDoMunicipio(props) {
      var mun = props.dado;
      if (!mun) { return COR_SEM_DADO; }
      if (camadaAtual === 'ipb') {
        return corIpb(mun.ipb_v3 === null || mun.ipb_v3 === undefined ? 0 : mun.ipb_v3);
      }
      return CORES_ARQUETIPOS[mun.arquetipo] || COR_SEM_DADO;
    }

    function renderizarLegenda() {
      if (!legendEl) { return; }
      if (camadaAtual === 'ipb') {
        var passos = [];
        for (var t = 0; t <= 1.001; t += 0.125) { passos.push(corIpb(t * 100)); }
        legendEl.innerHTML =
          '<div class="legend-scale">' +
          '<span>0</span>' +
          '<div class="legend-bar" style="background:linear-gradient(to right,' + passos.join(',') + ')"></div>' +
          '<span>100</span>' +
          '<span class="legend-title">IPB V3</span>' +
          '</div>' +
          '<div class="legend-item"><span class="sw" style="background:' + COR_SEM_DADO + '"></span> sem dado</div>';
      } else {
        var html = Object.keys(CORES_ARQUETIPOS).map(function (nome) {
          return '<div class="legend-item"><span class="sw" style="background:' + CORES_ARQUETIPOS[nome] + '"></span> ' + nome + '</div>';
        }).join('');
        html += '<div class="legend-item"><span class="sw" style="background:' + COR_SEM_DADO + '"></span> sem arquétipo / sem dado</div>';
        legendEl.innerHTML = html;
      }
    }

    function posicionarTooltip(event) {
      var margem = 14;
      var x = event.pageX + margem;
      var y = event.pageY + margem;
      if (x + tooltip.offsetWidth > window.scrollX + window.innerWidth - 8) {
        x = event.pageX - tooltip.offsetWidth - margem;
      }
      tooltip.style.left = x + 'px';
      tooltip.style.top = y + 'px';
    }

    function mostrarTooltip(event, d) {
      var mun = d.properties.dado;
      if (!mun) { return; } // lagoas/áreas sem dado: sem tooltip
      tooltip.innerHTML =
        '<strong>' + mun.nome_municipio + ' (' + mun.sigla_uf + ')</strong><br>' +
        'IPB V3: ' + fmtNumero(mun.ipb_v3) + '<br>' +
        'Rank V3: ' + (mun.rank_v3 === null || mun.rank_v3 === undefined ? '—' : mun.rank_v3) + '<br>' +
        'Arquétipo: ' + (mun.arquetipo || '—');
      tooltip.style.display = 'block';
      posicionarTooltip(event);
    }

    function esconderTooltip() {
      tooltip.style.display = 'none';
    }

    // Fronteira estadual: arco onde os dois polígonos vizinhos têm SIGLA_UF
    // diferente. a === b não é fronteira; b indefinido é borda externa
    // (litoral/fronteira do país), que não demarca estado.
    function filtroFronteiraEstadual(a, b) {
      return a !== b && !!b && a.properties.SIGLA_UF !== b.properties.SIGLA_UF;
    }

    return Promise.all([
      buscarJson('assets/malha/br_municipios_2022.topojson'),
      buscarJson('data/municipios.json')
    ]).then(function (resultados) {
      var topo = resultados[0];
      var dados = resultados[1];
      corIpb = d3.scaleSequential(d3.interpolateYlGnBu).domain([0, 100]);

      // join string -> string: CD_MUN (malha) com id_municipio (dados)
      var porId = new Map(dados.map(function (m) { return [m.id_municipio, m]; }));

      var colecao = topojson.feature(topo, topo.objects.BR_Municipios_2022);
      colecao.features.forEach(function (f) {
        f.properties.dado = porId.get(f.properties.CD_MUN) || null;
      });

      if (statusEl) {
        var semDado = colecao.features.filter(function (f) { return !f.properties.dado; }).length;
        statusEl.textContent = dados.length.toLocaleString('pt-BR') + ' municípios carregados' +
          (semDado ? ' · ' + semDado + ' áreas sem dado (corpos hídricos)' : '');
      }

      var projection = d3.geoMercator().fitExtent([[8, 8], [LARGURA - 8, ALTURA - 8]], colecao);
      var path = d3.geoPath(projection);

      var svg = d3.select(container).append('svg')
        .attr('viewBox', '0 0 ' + LARGURA + ' ' + ALTURA)
        .attr('preserveAspectRatio', 'xMidYMid meet');

      // Grupo que recebe a transformação de zoom/pan (wheel amplia, drag desloca).
      var gViewport = svg.append('g');

      gViewport.append('g')
        .selectAll('path')
        .data(colecao.features)
        .join('path')
        .attr('class', 'mun')
        .attr('d', path)
        .attr('fill', function (d) { return corDoMunicipio(d.properties); })
        .on('mousemove', function (event, d) { mostrarTooltip(event, d); })
        .on('mouseleave', esconderTooltip);

      // Fronteiras estaduais por cima dos municípios: linha escura fina, sem
      // preenchimento e sem reagir ao mouse.
      gViewport.append('path')
        .attr('class', 'fronteira-uf')
        .datum(topojson.mesh(topo, topo.objects.BR_Municipios_2022, filtroFronteiraEstadual))
        .attr('d', path);

      // O tooltip é posicionado por pageX/pageY (coordenadas de tela), então
      // continua certo sobre a transformação de zoom.
      var zoom = d3.zoom()
        .scaleExtent([1, 12])
        .on('zoom', function (event) {
          gViewport.attr('transform', event.transform);
        });
      svg.call(zoom);

      if (botaoReset) {
        d3.select(botaoReset).on('click', function () {
          svg.transition().duration(400).call(zoom.transform, d3.zoomIdentity);
        });
      }

      renderizarLegenda();

      botoesCamada.forEach(function (btn) {
        btn.addEventListener('click', function () {
          if (btn.dataset.layer === camadaAtual) { return; }
          camadaAtual = btn.dataset.layer;
          botoesCamada.forEach(function (b) {
            b.classList.toggle('active', b === btn);
          });
          svg.selectAll('.mun').attr('fill', function (d) { return corDoMunicipio(d.properties); });
          renderizarLegenda();
        });
      });

      return { svg: svg, zoom: zoom };
    }).catch(function (err) {
      if (statusEl) {
        statusEl.textContent = 'Erro ao carregar dados: ' + err.message;
        statusEl.classList.add('erro');
      }
      throw err;
    });
  }

  global.inicializarMapa = inicializarMapa;
})(window);

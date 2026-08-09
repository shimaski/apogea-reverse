# Apogea Reverse — Minimap Voxel 3D

Reverse engineering do visor minimap voxel 3D do jogo **Apogea**. Frontend em Three.js (r128) single-file carregável direto no navegador.

## Estrutura

```
apogea-reverse/
├── minimap.html         → O app inteiro (código + mundo + dados embutidos)
├── html-completo.txt     → Cópia do minimap.html (debug/diff)
├── js/three.min.js       → Three.js r128 (única dependência, CDN)
├── atlas/                 → Sprites/atlas usados pelos cards (stat_icons, item_atlas, mob_sprites)
├── data/                  → JSONs do runtime (entity_data, monster_stats, items, npc_trade, …)
├── monsters/              → Artwork das criaturas (`/monsters/<slug>.png`)
└── reports/               → Análise técnica do original (tecnologia, recursos externos)
```

## Como rodar

Como o app busca `/data`, `/atlas` e `/monsters` no runtime, sirva a pasta como site estático. Local rápido:

```powershell
# na raiz do projeto
python -m http.server 8000
# abra http://localhost:8000/minimap.html
```

O `three.min.js` é carregado do CDN (linha 7 do `minimap.html`) — offline não funciona sem trocar para o arquivo em `js/`.

## Controles

- **WASD + QE** — mover a câmera (QE = sobe/desce) · **Shift** = boost
- **Mouse drag** — olhar ao redor · **Scroll** — avançar/recuar
- **Up-to-floor** — slider que revela camadas de voxels (`minimap.html?goto=309,299&…`)
- Busca por NPC/creatura/lugar (`Find NPC…`), filtros de spawns, landmarks e NPCs
- Clique num sprite/landmark → card (bestiário, trading, loot) — usa `/data` e `/atlas`

## Minha wiki — puxador Discord

Este repo é **apenas do minimapa**. Os dados dos canais do Discord são coletados por um **puxador separado**:

- Repo: **`shimaski/apogawiki-discord-feed`** (privado)
- GitHub Action cada 4h → gera `discord/data/<canal>.json`
- Consumo pela wiki (Lovable) → ver **Passo 5** no README daquele repo

## Licença / origem

Dados e arte são do jogo Apogea; este repo é um estudo de reverse engineering. O `minimap.html` segue o formato publicado na wiki (apogeawiki.info).
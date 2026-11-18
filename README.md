# Pixel Plaza

Vitrine e painel de produtos da Pixel Plaza, em português. O projeto usa Flask e SQLite e inclui as tabelas de Gamepasses, Skins de frutas, Frutas físicas e Frutas permanentes.

## Recursos

- Vitrine responsiva com categorias, imagens e acesso ao Discord.
- Catálogo dinâmico alimentado pelo banco SQLite.
- Painel com login para criar, editar, destacar, ocultar e excluir produtos.
- Categorias de frutas físicas, gamepasses, skins de frutas, frutas permanentes e outros.
- Proteção CSRF nos formulários do painel.

## Executar localmente

Requer Python 3.10 ou mais recente.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edite `.env` e escolha valores próprios para `SECRET_KEY`, `ADMIN_USERNAME` e `ADMIN_PASSWORD`. O arquivo `.env` fica fora do Git.

```powershell
py app.py
```

Abra `http://127.0.0.1:5000` para ver a vitrine e `http://127.0.0.1:5000/admin/login` para gerenciar os produtos. O banco é criado em `instance/pixelplaza.sqlite` na primeira execução.

## Catálogo e imagens

O painel aceita preços como texto para preservar a formatação escolhida pela loja. Use o campo de imagem para informar um endereço `https://` de uma imagem de produto. As tabelas visuais de Gamepasses e Skins estão em `static/assets/`; os catálogos de frutas usam os ícones de `static/assets/items/` e os preços enviados.

Para publicar, use um serviço compatível com aplicações Python/Flask e configure as variáveis de ambiente nele. O repositório contém o código-fonte; o GitHub Pages não executa Flask.

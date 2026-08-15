# Crow Module Registry

Crow använder Python entry points i gruppen `crow.modules` för automatisk upptäckt.

En modul deklarerar exempelvis:

```toml
[project.entry-points."crow.modules"]
vent = "crow_vent.plugin:VentPlugin"
```

Backbone kan därefter lista installerade moduler:

```bash
crow module list
```

`ModuleRegistry` stoppar dubbla modul-ID:n. Ett modul-ID får endast representera en
aktiv implementation i samma runtime.

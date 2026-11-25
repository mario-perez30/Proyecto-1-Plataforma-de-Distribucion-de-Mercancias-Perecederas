# Guía de contribución

Trabajamos con **GitHub Flow**: `main` siempre funciona y todo cambio entra por una rama y un pull request (PR).

## Reglas de la rama `main`

- No se puede hacer push directo a `main`, ni siquiera los administradores.
- Un PR solo se puede fusionar si el pipeline de CI está en verde.
- Los PR se fusionan con **squash merge**: un commit por cambio en `main`.
- La rama se borra automáticamente al fusionar.

## Flujo de trabajo

```bash
# 1. Partir siempre de main actualizada
git switch main
git pull

# 2. Crear una rama con el prefijo adecuado
git switch -c feature/optimizador-ortools

# 3. Trabajar y hacer commits pequeños
git add <archivos>
git commit -m "feat(optimizador): primera versión con OR-Tools"

# 4. Subir la rama y abrir el PR
git push -u origin feature/optimizador-ortools
gh pr create --fill
```

Después, revisa que el CI pase, pide revisión a un compañero si el cambio es grande y fusiona desde GitHub.

## Nombres de rama

| Prefijo | Para | Ejemplo |
| --- | --- | --- |
| `feature/` | Funcionalidad nueva | `feature/mapa-rutas` |
| `fix/` | Corrección de un error | `fix/caducidad-pedidos` |
| `data/` | Cambios en la BD o en los datos | `data/precios-gasoleo-diciembre` |
| `docs/` | Documentación | `docs/manual-usuario` |
| `ci/` | Pipeline y automatización | `ci/tests-optimizador` |
| `refactor/` | Reorganizar código sin cambiar su comportamiento | `refactor/tools-comunes` |

## Mensajes de commit

Usamos [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/): `tipo(ámbito): descripción en minúsculas`.

Tipos: `feat`, `fix`, `data`, `docs`, `test`, `ci`, `refactor`, `chore`.

## Cambios en la base de datos

- **Los scripts de `database/` no se editan a mano si salen de `tools/`.** Cambia el generador y regenera: el CI comprueba que el resultado sea idéntico.
- Si añades tablas, vistas o datos, añade sus comprobaciones a `database/tests/verificar.sql`.
- Mantén la compatibilidad con MySQL 5.7, MySQL 8 y MariaDB: el CI los prueba todos.

## Documentación

Cada cambio relevante se refleja también en la memoria del proyecto: en la sección afectada, en la tabla de entregables y en el registro de cambios.

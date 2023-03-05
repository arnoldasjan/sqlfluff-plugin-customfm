# SQLFluff custom plugin

## How to start using SQLFluff with custom plugin

- This is a useful link for how to setup SQLFluff with dbt project: https://docs.sqlfluff.com/en/stable/configuration.html#dbt-project-configuration
- Link for rules reference: https://docs.sqlfluff.com/en/stable/rules.html

Inside your dbt project if you have virtual environment and just anywhere if you use global python packages you need 
to install these things:

1. Install sqlfluff `pip install sqlfluff`
2. Install relevant [dbt adapter](https://docs.getdbt.com/docs/available-adapters) for your database/data warehouse e.g. `pip install dbt-postgres`
3. Install sqlfluff dbt templater `pip install sqlfluff-templater-dbt`
4. Install custom plugin `pip install git+https://github.com/arnoldasjan/sqlfluff-plugin-customfm`

In the root of your dbt project:

5. Create `.sqlfluff` file for rules configurations.

```
[sqlfluff]
verbose = 2
templater = dbt
dialect = postgres

[sqlfluff:rules]
max_line_length = 140

[sqlfluff:layout:type:alias_expression]
# We want non-default spacing _before_ the alias expressions.
spacing_before = align
# We want to align them within the next outer select clause.
# This means for example that alias expressions within the FROM
# or JOIN clause would _not_ be aligned with them.
align_within = select_clause
# The point at which to stop searching outward for siblings, which
# in this example would likely be the boundary of a CTE. Stopping
# when we hit brackets is usually a good rule of thumb for this
# configuration.
align_scope = bracketed

[sqlfluff:indentation]
# See https://docs.sqlfluff.com/en/stable/layout.html#configuring-indent-locations
indented_on_contents = false
indented_on_ctes = false
template_blocks_indent = true

[sqlfluff:rules:L010]
capitalisation_policy = lower

[sqlfluff:rules:L014]
extended_capitalisation_policy = lower
```

6. Create `.sqlfluffignore` file to ignore specific folders to avoid linting for them.

Inside `.sqlfluffignore` usually these folders are excluded:
```
target/
# dbt <1.0.0
dbt_modules/
# dbt >=1.0.0
dbt_packages/
macros/
```

After this to start using sqlfluff run these commands:


`sqlfluff lint path_to_file_or_folder` and `sqlfluff fix path_to_file_or_folder`
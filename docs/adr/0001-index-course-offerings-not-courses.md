# Index Course Offerings, not merged Courses

The course data lists each course once per (technology, role) pair: 995 rows cover only 173 distinct titles, so a search often returns the same course several times. We index each row as its own Course Offering (keyed on `RowKey`) instead of merging rows into one Course with `products`/`roles` collections. Indexing rows as-is keeps the Table Storage → import wizard → indexer path that the project brief and rubric expect, and keeps facet counts truthful per technology and role. The cost is duplicate-looking results, which we accept and document.

## Considered Options

- **Merge into Courses before upload**: cleaner results, but needs a preprocessing model the wizard cannot reproduce, changes the document key, and moves away from the guided path.

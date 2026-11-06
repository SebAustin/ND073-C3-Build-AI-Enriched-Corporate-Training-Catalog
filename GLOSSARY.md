# Corporate Training Catalog

A single searchable catalog that lets employees find learning resources across external course providers, the company's internal Moodle training, and a curated library of research papers.

## Courses

**Course Offering**:
One course as listed for one technology and one role; a single course title appears as several Course Offerings.
_Avoid_: Course row, record, listing

**Source**:
The provider a Course Offering comes from: MS Learn, Udacity, or Company Moodle.
_Avoid_: Provider, origin, partition

**Course Type**:
The format of a Course Offering, determined by its Source: Module (MS Learn), Nanodegree (Udacity), or Internal (Company Moodle).
_Avoid_: Kind, category

**Technology**:
The product or platform a Course Offering teaches (e.g. Azure, GitHub, Dynamics 365).
_Avoid_: Product (in user-facing language)

**Rating**:
The average learner score of a Course Offering, alongside its Rating Count.
_Avoid_: Score, stars

**Duration**:
The expected learning time of a Course Offering, expressed in hours regardless of how its Source states it.
_Avoid_: Length, time

**Unrated**:
A Course Offering with no learner ratings; it has no Rating rather than a Rating of zero.

**Skill**:
A key phrase drawn from a Course Offering's description, describing what the learner will be able to do.
_Avoid_: Tag, keyword

## Internal training

**Instructor**:
A company employee who teaches Internal Course Offerings.
_Avoid_: Teacher, trainer, author

**Instructor Profile**:
The company-maintained description of an Instructor, surfaced with every Internal Course Offering they teach.
_Avoid_: Bio, instructor record

## Curated Library

**Curated Library**:
The company-selected set of open-access journal articles relevant to its big-data work.
_Avoid_: Papers, research, documents

**Paper**:
One open-access journal article in the Curated Library.
_Avoid_: Article (except as the Springer lookup input), PDF, document

**Publication**:
The journal a Paper appeared in, along with its Publisher, Publication Date, and DOI.
_Avoid_: Journal (ambiguous with the PDF file)

## Known data gaps

**Popularity** and **Review** are named in the brief but are not present in the course data; they are not part of the catalog.

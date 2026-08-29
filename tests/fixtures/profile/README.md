# A synthetic profile directory

**Standing:** firm. Values are invented and must never be quoted as a result. Last checked
2026-08-29.

Deliberately tiny, deliberately not this proband. It exists so the exploration toolkit can
be tested end to end — readers, profile assembly, checks, every view and the report shell —
without any real dataset present and without any patient-derived number entering the
repository.

The values are invented and internally consistent: a small callset with a healthy
transition/transversion ratio, one chromosome pushed off diploid allele balance so the
aneuploidy check has something to catch, one gene with a suppressed-call excess, and two
FASTQ files worth of reads. Nothing here should ever be quoted as a result.

Filenames follow the default `ProfileLayout`, which is also the point: reading a
differently-named profile directory is a layout swap, and this directory proves the
default one is not hard-coded anywhere.

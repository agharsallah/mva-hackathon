# The bioinformatics toolchain is installed with micromamba

**Standing:** provisional — whatever installs cleanly without root. Worth revisiting when
the work moves to Modal.

The development machine has no passwordless sudo, so `apt` is unavailable, and the Ubuntu
repositories carry `bcftools` at a version behind what we need anyway. Docker is present but
puts a container boundary between the tools and an 80 GB dataset for no benefit here.

`tools/setup-env.sh` installs micromamba into `~/.local` and creates an environment holding
bcftools, samtools, htslib, seqkit and fastp. The same command works unchanged on a Modal
container later, which is where the alignment and re-calling work will run.

# NOT BUILT END TO END: the HPC sandbox refuses the build step (fakeroot %post). Verified only: base digest pulls,
# apt list resolves via the archive.debian.org fallback (simulated), package list covers all 34 DESCRIPTION deps.
# The first laptop build is the real test. See ../README.md.
# scSVA @ c9e8fd6 (2019-03-26) in a period-correct R 3.6.3 + Python 3.6 / vaex 2.0.3 image.
# linux/amd64 ONLY (rocker/r-ver:3.6.3 has no arm64 image; R 3.6 and vaex 2.x have no macOS arm64 builds).
# On an Apple Silicon Mac: Docker Desktop with "Use Rosetta for x86_64/amd64 emulation" on, then
#   docker build --platform linux/amd64 -t scsva:c9e8fd6 .
#   docker run --platform linux/amd64 --rm -p 3838:3838 -v /path/to/scsva_inputs:/data:ro scsva:c9e8fd6
# then open http://localhost:3838 and pick files under /data in the file choosers.
FROM rocker/r-ver:3.6.3@sha256:9414f76c5f91f24617b5275b8fe4f4ff1313b3b10698a525cac0063c01f2ca6d

ARG SCSVA_COMMIT=c9e8fd6b280910eadf9daba35badcf6933c7f353
ARG CRAN_SNAPSHOT=https://packagemanager.posit.co/cran/2020-04-20
ARG MICROMAMBA_VERSION=1.5.8

COPY apt-sources.sh /tmp/apt-sources.sh
RUN bash /tmp/apt-sources.sh && apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl bzip2 git libcairo2-dev libxt-dev libmagick++-dev libcurl4-openssl-dev \
      libssl-dev libxml2-dev libz-dev fonts-dejavu-core fontconfig \
 && rm -rf /var/lib/apt/lists/*

# Python backend (vaex 2.0.3, python 3.6) via micromamba, pinned by scsva-py.yml
COPY scsva-py.yml /tmp/scsva-py.yml
RUN curl -fsSL https://micro.mamba.pm/api/micromamba/linux-64/${MICROMAMBA_VERSION} | tar -xj -C /usr/local bin/micromamba \
 && MAMBA_ROOT_PREFIX=/opt/mamba /usr/local/bin/micromamba create -y -p /opt/pyenv -f /tmp/scsva-py.yml \
 && /usr/local/bin/micromamba clean -a -y
ENV PATH=/opt/pyenv/bin:$PATH RETICULATE_PYTHON=/opt/pyenv/bin/python

# R packages from one dated CRAN snapshot; rhdf5 from Bioconductor 3.10 (the R 3.6 release)
COPY install_r.R /tmp/install_r.R
RUN Rscript /tmp/install_r.R "${CRAN_SNAPSHOT}" \
 && echo 'options(bitmapType = "cairo")  # headless: Shiny png() needs cairo, there is no X11' >> /usr/local/lib/R/etc/Rprofile.site

# scSVA itself at the pinned commit
RUN git clone https://github.com/klarman-cell-observatory/scSVA.git /opt/scSVA \
 && git -C /opt/scSVA checkout ${SCSVA_COMMIT} \
 && R CMD INSTALL /opt/scSVA

EXPOSE 3838
CMD ["Rscript", "-e", "shiny::runApp(system.file('scSVA', package='scSVA'), host='0.0.0.0', port=3838, launch.browser=FALSE)"]

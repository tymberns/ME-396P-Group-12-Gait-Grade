FROM mambaorg/micromamba:latest

USER root
COPY packages.txt /tmp/packages.txt
RUN apt-get update \
 && grep -v '^\s*#' /tmp/packages.txt | xargs -r apt-get install -y --no-install-recommends \
 && apt-get install -y --no-install-recommends libgl1 libglu1-mesa \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir /app && chown $MAMBA_USER:$MAMBA_USER /app

USER $MAMBA_USER
COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -f /tmp/environment.yml && micromamba clean --all --yes

ARG MAMBA_DOCKERFILE_ACTIVATE=1
ENV MPLBACKEND=Agg
WORKDIR /app
COPY --chown=$MAMBA_USER:$MAMBA_USER . /app

EXPOSE 8501
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--server.maxUploadSize=300"]

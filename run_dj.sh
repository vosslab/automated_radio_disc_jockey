#!/bin/bash

export PYGAME_HIDE_SUPPORT_PROMPT='hide'

name="ollama_serve"
if screen -list | grep -q "\.${name}"; then
  echo "Session '$name' already running."
else
  screen -dmS "$name" bash -c "ollama serve"
  sleep 3
fi

./disc_jockey.py \
  -n 24 \
  -d $HOME/Documents/ipod/ \
  -r 1.2

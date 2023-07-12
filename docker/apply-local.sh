#!/bin/bash

cd $(hostname | tr '[:upper:]' '[:lower:]') && ./apply.sh

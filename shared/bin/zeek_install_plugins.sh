#!/bin/bash

# Copyright (c) 2021 Battelle Energy Alliance, LLC.  All rights reserved.

if [ -z "$BASH_VERSION" ]; then
  echo "Wrong interpreter, please run \"$0\" with bash"
  exit 1
fi

SPICY_DIR=${SPICY_DIR:-/opt/spicy}
ZEEK_DIR=${ZEEK_DIR:-/opt/zeek}

# going to clone under /usr/local/src
SRC_BASE_DIR="/usr/local/src"
mkdir -p "$SRC_BASE_DIR"

#
# get_latest_github_tagged_release
#
# get the latest GitHub release tag name given a github repo URL
#
function get_latest_github_tagged_release() {
  REPO_URL="$1"
  REPO_NAME="$(echo "$REPO_URL" | sed 's|.*github\.com/||')"
  LATEST_URL="https://github.com/$REPO_NAME/releases/latest"
  REDIRECT_URL="$(curl -fsSLI -o /dev/null -w %{url_effective} "$LATEST_URL" 2>/dev/null)"
  if [[ "$LATEST_URL" = "$REDIRECT_URL"/latest ]]; then
    echo ""
  else
    echo "$REDIRECT_URL" | sed 's|.*tag/||'
  fi
}

#
# clone_github_repo
#
# clone the latest GitHub release tag if available (else, master/HEAD) under $SRC_BASE_DIR
# release tag/branch can be overriden by specifying the branch name with after the URL delimited by a |
#
function clone_github_repo() {
  URL_PARAM="$1"
  URL_BRANCH_DELIM='|'
  URL_BRANCH_DELIM_COUNT="$(awk -F"${URL_BRANCH_DELIM}" '{print NF-1}' <<< "${URL_PARAM}")"
  if (( $URL_BRANCH_DELIM_COUNT > 0 )); then
    REPO_URL="$(echo "$URL_PARAM" | cut -d'|' -f1)"
    BRANCH_OVERRIDE="$(echo "$URL_PARAM" | cut -d'|' -f2)"
  else
    REPO_URL="$URL_PARAM"
    BRANCH_OVERRIDE=""
  fi
  if [[ -n $REPO_URL ]]; then
    if [[ -n $BRANCH_OVERRIDE ]]; then
      REPO_LATEST_RELEASE="$BRANCH_OVERRIDE"
    else
      REPO_LATEST_RELEASE="$(get_latest_github_tagged_release "$REPO_URL")"
    fi
    SRC_DIR="$SRC_BASE_DIR"/"$(echo "$REPO_URL" | sed 's|.*/||')"
    rm -rf "$SRC_DIR"
    if [[ -n $REPO_LATEST_RELEASE ]]; then
      git -c core.askpass=true clone --depth=1 --single-branch --branch "$REPO_LATEST_RELEASE" --recursive --shallow-submodules "$REPO_URL" "$SRC_DIR" >/dev/null 2>&1
    else
      git -c core.askpass=true clone --depth=1 --single-branch --recursive --shallow-submodules "$REPO_URL" "$SRC_DIR" >/dev/null 2>&1
    fi
    [ $? -eq 0 ] && echo "$SRC_DIR" || echo "cloning \"$REPO_URL\" failed" >&2
  fi
}

# don't consume as many resources when building spicy-analyzers, even if it's slower.
# https://github.com/zeek/spicy-analyzers/pull/60
export SPICY_ZKG_PROCESSES=1

# install Zeek packages that install nicely using zkg
ZKG_GITHUB_URLS=(
  "https://github.com/cisagov/icsnpp-bacnet"
  "https://github.com/cisagov/icsnpp-bsap"
  "https://github.com/cisagov/icsnpp-dnp3"
  "https://github.com/cisagov/icsnpp-enip"
  "https://github.com/cisagov/icsnpp-ethercat"
  "https://github.com/cisagov/icsnpp-modbus"
  "https://github.com/corelight/callstranger-detector"
  "https://github.com/corelight/CVE-2020-16898"
  "https://github.com/corelight/CVE-2021-31166"
  "https://github.com/corelight/CVE-2021-41773"
  "https://github.com/corelight/pingback"
  "https://github.com/corelight/SIGRed"
  "https://github.com/corelight/zeek-community-id"
  "https://github.com/mitre-attack/bzar"
  "https://github.com/mmguero-dev/cve-2020-0601|zeek-v4.1-compatibility"
  "https://github.com/mmguero-dev/cve-2020-13777|zeek-v4.1-compatibility"
  "https://github.com/mmguero-dev/CVE-2021-38647|zeek-v4.1-compatibility"
  "https://github.com/mmguero-dev/GQUIC_Protocol_Analyzer|zeek-v4.1-compatibility"
  "https://github.com/mmguero-dev/ripple20|zeek-v4.1-compatibility"
  "https://github.com/mmguero-dev/spicy-analyzers|main"
  "https://github.com/mmguero-dev/zeek-af_packet-plugin|master"
  "https://github.com/mmguero-dev/zeek-EternalSafety|zeek-v4.1-compatibility"
  "https://github.com/mmguero-dev/zeek-plugin-profinet|zeek-v4.1-compatibility"
  "https://github.com/mmguero-dev/zeek-plugin-s7comm|zeek-v4.1-compatibility"
  "https://github.com/mmguero-dev/zeek-plugin-tds|zeek-v4.1-compatibility"
  "https://github.com/mmguero-dev/zeek-sniffpass|zeek-v4.1-compatibility"
  "https://github.com/mmguero-dev/zeek-xor-exe-plugin|zeek-v4.1-compatibility"
  "https://github.com/mmguero-dev/zerologon|zeek-v4.1-compatibility"
  "https://github.com/precurse/zeek-httpattacks"
  "https://github.com/salesforce/hassh"
  "https://github.com/salesforce/ja3"
)
for i in ${ZKG_GITHUB_URLS[@]}; do
  SRC_DIR="$(clone_github_repo "$i")"
  [[ -d "$SRC_DIR" ]] && zkg install --force --skiptests "$SRC_DIR"
done

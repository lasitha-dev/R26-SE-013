#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCREENS_DIR="$ROOT_DIR/screens"

mkdir -p "$SCREENS_DIR"

fetch_screen() {
  local screen_id="$1"
  local title="$2"
  local html_url="$3"
  local img_url="$4"

  local out_dir="$SCREENS_DIR/$screen_id"
  mkdir -p "$out_dir"

  printf '%s\n' "$title" > "$out_dir/title.txt"

  echo "Downloading HTML for $screen_id..."
  curl -L "$html_url" -o "$out_dir/screen.html"

  echo "Downloading screenshot for $screen_id..."
  curl -L "$img_url" -o "$out_dir/screenshot.png"

  cat > "$out_dir/meta.json" <<EOF
{
  "id": "${screen_id}",
  "title": "${title}",
  "htmlDownloadUrl": "${html_url}",
  "screenshotDownloadUrl": "${img_url}"
}
EOF
}

fetch_screen \
  "263e4e6e9f404fa1922143b8eb9f8c64" \
  "Wellness & BCS Dashboard - ADRS Core" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzBiOGVkZjg5YTQ4ZDQxMjU4NmQ1NmE3M2E1Y2FkMjAzEgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0uj7VyCCK5kDQVcjshGSlckJAYPCktzXqIgc5XrntH1ICma2CZUvRbd0oAH2rkVSjl-T3LqxU8EjzR8GxhtaqePVo46EFRB4g3ST03Vwbgi5exD7XLcorb5S8iKYeSCdUBtUgEu-1qDtfhuKLAlPecTwykr6rfzFYJI4X0EiuXgohJTNZwy7UtwVOothoN6lL1q1oLtVn5Fu0pd_aR0Pl9Q1XrN1GiTVJnYtlVwhjxqEcvrKlScYUh24D6wD"

fetch_screen \
  "3e4b223ff6914859a58cf616b4c1d5d0" \
  "Registration Success - ADRS Core" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2FmMmE2YjY3MzFjYjRhYmE4NmJjZTViM2ZhNmFkZWNmEgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0ug86_a3Bow-KACo89df3yWYIq7eFyP2IZEmjy_RE_v9wjjqOdWQxUWD-lX9xGkLTKxTJDp9e452iYoRxF5dh4PPzTfO8SRlc56udCwoM8dKOm4bdBIBVjf4ZlkWt0tGKg7sQGpZ7HtV0_YGJB-GHe761qETK7Zx6u4nhNMIGsMPTV3guwPabtH7hLM4WWDTxv0GDRpVhDDlFJEKQMnuwuk0t5N_NlRU8XDV2E-i2opYw_d0RXszKiR3pgmD"

fetch_screen \
  "5aeac88ec69740d888e38cad2993bb81" \
  "System Login - ADRS Core" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2FkMDc0MzQ0YTg0ODQyNTA4YTNmMWQ3ODUyYjI1YmVkEgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0uhVfCWUOfFjiWzJM1mEumif2aSBcBm0sicJLowdj_JDyMP_Hi9Ow6ZTggY09C-Fh5DV4NjphGM3ojZu-w-R5dYTIUWbeVLkMjQg5b9ZXnv4XR99cOa9zOwcZX62atDn89uhHGvyz_fbipXDBymnMMz0NVz09Zh51N7iG3IwMPW0yB8xJfqhtM3A_hhuFiBypWLM7JLKuprnyTNgYzw-Zv01b0jmLFRtg0Hut_WCDrpt5Tgh-znuE0FfEPnT"

fetch_screen \
  "77df6a1df9054554be9b3f5dcd7fba6e" \
  "ADRS Core - Registration Landing Page" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2U2NzNmODFjNzMxZTRjOGJhZjJlMmZmMjA4MGVlZjUwEgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0ugyCuQjuoCRH6e2_ZgNSS_S5FXUgeuPZ6G72fS12-PW3rrMlzPZp82z69q_yQRNPUJ7EcALAlq2tL655zaOo6DhQIHza47TEu1Tjsd6EvOHglLDhfmJQbFOVF_QUH_uIgQWAccrqpFgyaQCYHC-jG7ldgNGShrDLU0GGocdf1hw6TvSzTO_5HPDCmESKVyOYHFjoObKR-g-JgCKpuo1QGQcUTuDlMl0soNpqIz33kgRE5Y8SzpTvkPGCanY"

fetch_screen \
  "e9c8fb4a80fb428394988abfe6936a17" \
  "Password Reset - ADRS Core" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzgyMjMxNDQ1ZmYyMzQ0ZGY5ZTVhMmQ0MDFhYjQ1YmE5EgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0uhxtr8ITp7hCxVUEYc6-VhebLT5jQjsTGr7ZSRfc49OGmM27dFPnNKpBIwyMG4fy98k-t8HMLnjnBDaSoAvDhxwNF7PdAUTkoabJ5poC0D_c72TETuEs7Bg-r4B-lY1KSBs0HBnVFHyHvpRcwBtZNNj-uH3oc-oFUZqdMI7eo60nIrSW85p9ggi3HmK974oJmuC2aSJWj4wzyUJbFj3RAa2LcIgL2i7xSzu2fE1oG5oATGOo2uIW5HkoJjK"

fetch_screen \
  "e8f7caf4eb8e4ff69afb042fe9455f8b" \
  "Settings & Farm Configuration - ADRS Core" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzA3OGY1ZjQ4MDBjNzQ5NzZiZmRhZGY5ZWZlNzhlYWQxEgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0uj1mTxBuaAW1xkXe8o3qPhXlq2rt-OENjSi21FEs2tXFSfDJXyj0PAIMe6Gr7oq0DitCDoeG4y1F7otuAIDBGOvbwOF2obmlVAl3p5HjR2-6EEBw-ct66KoTDe14wubytJXLoMivhhuDO5WAJj0MwcKA0Rh3J2dxnjmfscKzSJ0HmNqkQOo08Crt39SoViTb--Zj4LNjiEJDYX3o8ohOSzjwauEzCVE4-iZ30PYPOzkHKmwsOlRELz1Lvk2"

fetch_screen \
  "41036632330c402a9d3cff219b726166" \
  "Herd Registry - Synchronized Sidebar" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2VjOWIwZmFiYjI2MzQ3ZGRhZjExZjIxODBlM2E5OTNkEgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0ujvKDumxNmlf-VpKECr6kMaVFSc40wMqEcUI8rfxPlcZ3MlFF_DbRaBUb5n1BRu16WxM2JSZ7EFL8uqHk2skYUxqMJQn73kkxaiZL9WJZmTv9bBFhNK7aDkbbPPWD6ooblFVl1ys3rnNOMR-KMFkp1LUQeTSYmdFHyAhVdkGBxXUAOlwpfr4g2vT4wrqOvxLO_uNW1JR40zE0nE0GiWIv9P6cxxiJbEC7VR34MiclDo6Jc9-jBU_J5xojc"

fetch_screen \
  "06fac8446e0646a7a72fa71f360352c5" \
  "Animal Profile: #BT-8842 - Updated Icon" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzAwMDY1MGY4NGE3NDFiOGMwMDMwMmJjNjRkMDk5Y2Q2EgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0uh2s0WBcS9LinXbEHq2fv2Vjs6Hpf3wtQarldsVBjtXG-ceryxes-DzDrkrED3XbqrO_7SdVkYvhyiIHnK5zxx1odRkZz0nEIgvsTjFVY4T3nuldWUllZckFjXBPl4UJflp1OYekEVf_sGp0d7EzPYbYccV6oDlIG7rmWCVbjiChhOEsjBweEW_GCFm_LIS5ubOaf6jil15NFxn1-XS9IGvy_vNAF_wqPA69rjs2k6WGvfb2qRIAtWuS1m_"

fetch_screen \
  "d6e9ca15d7174d00915dfecfdd3d3df0" \
  "Add New Animal - ADRS Core Registry" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzczYWE5MTYxMDZiOTQ5MzU4NDA3YjQxYjA5MDhlMDMxEgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0uhCCtZaZWKmCbL-Mf0ztSh6BHrQxLoxGBymuLnW5qCmUbIP5IET4qfffXEzx2nCQqx7nNONorHfPjr8FnIOC3X0VF6uoYvqXX-SJaT9OTrqkYyyu8BlaM6lWpPPxDmHHafs3RF7kSSUFGu1mB91WuRv3WTfqRhl6Q8zw1ErjrfeeMLpeX4AHSSOkG3e7bqRJ1qd31SOmH3dXNP3lMi1tSM1GdJtaSq24tJNEBzxJyp-iMyTfYdBXgpWMo68"

fetch_screen \
  "f4853c2b4d4d4291892825570028900a" \
  "Wellness Data Intake - ADRS Core (Updated)" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2U4NzA3MDgxNjYzZjQ5MjA5MjI2MmE2MzMyMDNkOWJmEgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0ugeTViU3bZLtpEUjd0-xqym1R-IABErx7_2xsCO_1uBBapPnPRTIRJxNoW57NXQFLKZYwVtLha601erlXUn4lfBMMD7lxU9FZWQyKa4bMYRC__ZD8IDdXiGn0j7HbnU0ztmdFU5qp5Ey7SsIJLpnk7hiz9Jf1dolEALTihlMmwMvDefu_l9e3rCTBxJCMzBI-W1KWU6nv3z4QQZrgkoVyOTDR-2CE-MHQ7HdJbRk8ISPmc3fBoDLPvyrWpe"

fetch_screen \
  "878b5f5cdf63490fb2c149f989d50ab4" \
  "7-Day Wellness Triage Scan - ADRS Core" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2FmMjUwYzk0NjU0ZjQyNDM4MTJmMjYwMDE2OTY3ZThmEgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0ugI9g-C7mE3pGM0BfQTL7RJcoJdyp7a1mv8JcY6yiP0b8jI6sqxidqEwsgBG_iHjrcTuonX-eL9QnfcTDnPeCuMTfY05IjNjXZgwCJ-pFFOBXg6Lb5Sk2PFWcwbEiJtE9x3v_0xO4s2O8_8HALeq7PBu5-0BG8PskrBZ5h24IXKTC0s4iBkH-soNdct7YPcRCq522jg2OpsBD3un7AygKOQ5aUpiKvYRbX0WlaLPubKs8jkFEw4X_bzzdI"

fetch_screen \
  "b052fed055594250822829786a818d35" \
  "AI Wellness Report - Diagnostic Triage Results" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzlhNzdlMmRiYTdiNTQ5MDU5Mjc4ZjI0NjQwNDNmOTA0EgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0uiuB082yqvfFiQ76Vugznh1cxmAfkQiBo6EnVFOhScZZHFHLMaPVbDdp9NxtYR2_3duNnSv1onvNQzuDc9RDYZvOOPpoXCn8L_20AoXXoIHFD9oe4IQ6GI78Zhh34u6vagBgbgN5wEARlY6nCZVSkC2JEigTLq5_8m0HntjQdJgUBoIz7iwWteT7Xhicc7zuV8W7skSS1iEU6oLJLRZvpRglSYTVgeC7HjaQv8lJREPr7HLwwImi61R4lx6"

fetch_screen \
  "65f34931f0bf4368a4e5c93b307490c9" \
  "Notifications & AI Alerts Center - ADRS Core" \
  "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzAyMjA4MmUyNWFiODQyYjc5Mjk0MjdhZjBmNmQzZWM5EgsSBxCY5aiJkA0YAZIBJAoKcHJvamVjdF9pZBIWQhQxODA5NDY0NzgyNDk5NjkwODA4NA&filename=&opi=89354086" \
  "https://lh3.googleusercontent.com/aida/ADBb0ujgYBq09OjCARikeGp3u8FNaT08_03pivoOtYIlkCJ0obkwtT_ZijGh2I8cXITv3x0Sq50tXDHoFOM6EySqpECG5RuH-qoz4WUdlKgFoxdFXjytlS1pbOjJL02YtOmIGlJyXKB3K3tILhZzhULGwPxeK8PjGccH6ibkuJiXJUXA8SmnfNSiXtnoAjcpDTTgQck-B7-835hkfqm5OpZs1J8f68D-fO2Ybdgasyi57ycEUj4OMX-8T2j0AVE"

echo "Done. Files written under: $SCREENS_DIR"

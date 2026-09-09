#!/usr/bin/env bash
# 安装技能库:源库 skills/(域结构,唯一事实)→ .claude/skills(域结构) + .zcode/skills(扁平,运行时)
# 注意:本环境运行时同步可能带移动语义,装后以 _archive 备份为准可随时恢复
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# .claude(域结构镜像)
DEST="$ROOT/.claude/skills"; mkdir -p "$DEST"
for domain in ideate write revise audit ops; do
  mkdir -p "$DEST/$domain"
  find "$ROOT/skills/$domain" -mindepth 1 -maxdepth 1 -type d ! -name "$domain" | while read -r d; do
    name=$(basename "$d"); rm -rf "$DEST/$domain/$name"; cp -r "$d" "$DEST/$domain/$name"
  done
  cp "$ROOT/skills/$domain/SKILL.md" "$DEST/$domain/SKILL.md"
done
echo "已装 $DEST(域结构)"

# .zcode(扁平:每技能顶层目录;用find防glob失效)
if [ -d "$ROOT/.zcode" ]; then
  Z="$ROOT/.zcode/skills"; mkdir -p "$Z"
  for domain in ideate write revise audit ops; do
    find "$ROOT/skills/$domain" -mindepth 1 -maxdepth 1 -type d | while read -r d; do
      name=$(basename "$d"); rm -rf "$Z/$name"; cp -r "$d" "$Z/$name"
    done
    rm -rf "$Z/$domain"; mkdir -p "$Z/$domain"; cp "$ROOT/skills/$domain/SKILL.md" "$Z/$domain/SKILL.md"
  done
  echo "已装 $Z(扁平,$(find "$Z" -name SKILL.md | wc -l)个SKILL.md)"
fi

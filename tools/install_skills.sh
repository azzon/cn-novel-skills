#!/usr/bin/env bash
# 安装技能库 v2: 源库 skills/(域结构,唯一事实源SSOT)→ .claude/skills(域结构) + .zcode/skills(扁平,运行时)
# v2变更(audits/03): 动态发现域(不再写死5个)、孤儿清理(只增不减→收敛语义)、缺SKILL.md即fail-fast
# 使用前提: skills/ 必须已是最新(若.zcode更新而skills/落后,先做反向回灌,严禁直接运行本脚本回退版本)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

DOMAINS=$(find "$ROOT/skills" -mindepth 1 -maxdepth 1 -type d | while read -r d; do basename "$d"; done | sort)
[ -n "$DOMAINS" ] || { echo "错误: skills/ 下无域目录"; exit 1; }
for domain in $DOMAINS; do
  [ -f "$ROOT/skills/$domain/SKILL.md" ] || { echo "错误: 域 $domain 缺入口SKILL.md(fail-fast)"; exit 1; }
done

# .claude(域结构镜像)
DEST="$ROOT/.claude/skills"; mkdir -p "$DEST"
for domain in $DOMAINS; do
  mkdir -p "$DEST/$domain"
  find "$ROOT/skills/$domain" -mindepth 1 -maxdepth 1 -type d ! -name "$domain" | while read -r d; do
    name=$(basename "$d"); rm -rf "$DEST/$domain/$name"; cp -r "$d" "$DEST/$domain/$name"
  done
  cp "$ROOT/skills/$domain/SKILL.md" "$DEST/$domain/SKILL.md"
done
# 孤儿清理: 目标域内源库不存在的叶目录
for domain in $DOMAINS; do
  find "$DEST/$domain" -mindepth 1 -maxdepth 1 -type d ! -name "$domain" | while read -r d; do
    name=$(basename "$d")
    [ -d "$ROOT/skills/$domain/$name" ] || { rm -rf "$d"; echo "清理孤儿[$DEST]: $domain/$name"; }
  done
done
# 清理源库已删除的整域
find "$DEST" -mindepth 1 -maxdepth 1 -type d | while read -r d; do
  name=$(basename "$d")
  echo "$DOMAINS" | grep -qx "$name" || { rm -rf "$d"; echo "清理孤儿域[$DEST]: $name"; }
done
echo "已装 $DEST(域结构)"

# .zcode(扁平: 每叶技能顶层目录 + 域入口目录)
if [ -d "$ROOT/.zcode" ]; then
  Z="$ROOT/.zcode/skills"; mkdir -p "$Z"
  for domain in $DOMAINS; do
    find "$ROOT/skills/$domain" -mindepth 1 -maxdepth 1 -type d | while read -r d; do
      name=$(basename "$d"); rm -rf "$Z/$name"; cp -r "$d" "$Z/$name"
    done
    rm -rf "$Z/$domain"; mkdir -p "$Z/$domain"; cp "$ROOT/skills/$domain/SKILL.md" "$Z/$domain/SKILL.md"
  done
  # 孤儿清理: 运行时里源库不存在的顶层目录(=游离的旧技能)
  find "$Z" -mindepth 1 -maxdepth 1 -type d | while read -r d; do
    name=$(basename "$d")
    if ! echo "$DOMAINS" | grep -qx "$name"; then
      find "$ROOT/skills" -mindepth 2 -maxdepth 2 -type d -name "$name" | grep -q . || {
        mkdir -p "$Z/.orphans"; mv "$d" "$Z/.orphans/$name"; echo "孤儿隔离(不删除,W6): $name → .orphans/"
      }
    fi
  done
  echo "已装 $Z(扁平,$(find "$Z" -name SKILL.md | wc -l)个SKILL.md)"
fi

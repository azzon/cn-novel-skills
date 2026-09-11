#!/bin/bash
# commit-msg hook: 章节提交信息必须含staged章号之一(audits/10:git log作二级信源须机器可解析)
# 合规格式示例: 第080章《长风号》定稿(0FAIL):... / ch080: ...
MSG_FILE="$1"
cd "$(git rev-parse --show-toplevel)" || exit 1
NUMS=$(git -c core.quotepath=false diff --cached --name-only --diff-filter=ACM 2>/dev/null | grep -E '^text/卷[^/]+/第[0-9]+章\.md$' | grep -o '第[0-9]*章' | grep -o '[0-9]*')
[ -z "$NUMS" ] && exit 0   # 非章节提交不约束
MSG=$(cat "$MSG_FILE")
for N in $NUMS; do
    if echo "$MSG" | grep -qE "第0?${N}章|^ch0?${N}[^0-9]"; then
        exit 0
    fi
done
echo "commit-msg: 提交含章节文件,但信息未含任何staged章号(如: 第${NUMS}0章《标题》...)" >&2
exit 1

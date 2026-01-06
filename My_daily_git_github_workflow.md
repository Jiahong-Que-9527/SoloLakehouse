# 我的日常 Git + GitHub 工作流

## 1) 我的日常 Git + GitHub 工作流（开源项目维护者视角）

### A. 每天开始：同步 + 检查状态（2 分钟）

1. **进入主分支**（main 或 master）

   * `git switch main`
2. **同步远端最新代码**

   * `git pull --ff-only`
     （只允许 fast-forward，避免你本地误制造成 merge commit）
3. **检查工作区是否干净**

   * `git status`
4. （可选）看一眼最近提交

   * `git log --oneline -n 10`

> 目标：确保你从一个“干净且最新”的 main 开始工作，减少后续冲突。

---

### B. 开始一个任务：从 Issue 出发建分支（5 分钟）

你开源项目每天的工作最好用 **Issue 驱动**（哪怕你自己给自己开 Issue）。

1. **先建 Issue**

   * Bug：Bug report
   * 功能：Feature request
   * 文档：Docs
   * 重构：Refactor
2. **从 main 拉分支**

   * 分支命名建议：

     * `feat/<short-topic>`
     * `fix/<short-topic>`
     * `docs/<short-topic>`
     * `refactor/<short-topic>`
3. **创建并切换分支**

   * `git switch -c feat/add-cli-export`

> 目标：每一个改动都能对应一个 Issue（可追踪、可讨论、可复现）。

---

### C. 编码阶段：小步提交 + 自测（循环执行）

这是你一天里最频繁的循环：

1. 写代码 / 改文档
2. **本地测试 / lint / format**
3. 查看改动

   * `git diff`
4. 暂存（尽量精确）

   * `git add -p`（强烈推荐，避免把无关改动提交进去）
5. 提交

   * `git commit -m "feat: add export command"`
6. （随时）查看提交历史

   * `git log --oneline --decorate -n 10`

> 目标：**小提交、可回滚、可审查**。这是开源维护最省心的方式。

---

### D. 推送到 GitHub：触发 CI + 开 PR

1. 推送分支

   * `git push -u origin feat/add-cli-export`
2. 在 GitHub 创建 PR（Pull Request）
   PR 里写清楚：

   * 关联 Issue（`Closes #12`）
   * 改了什么、为什么
   * 怎么测试的
   * 是否有 breaking changes
3. 等 CI 通过（build/test/lint）
4. 自己 review（maintainer 自检）

   * 看 diff 有没有混进无关改动
   * 文档是否需要同步更新
   * 版本号、变更日志是否需要更新

> 目标：PR 是你项目的“变更审计记录”，未来你回头看会非常省时间。

---

### E. 合并策略：尽量 squash 合并，让 main 干净

对于个人开源项目，我推荐：

* **Squash and merge**（把分支上的多个小提交压成一个清晰提交）
* PR 标题就是最终 main 上的提交信息

合并前：

1. 确保分支是最新的 main（减少冲突）

   * `git fetch origin`
   * `git rebase origin/main`（或直接 GitHub 上 update branch）
2. CI 绿灯
3. 合并（squash）

合并后：

1. 切回 main 并同步

   * `git switch main`
   * `git pull --ff-only`
2. 删除本地分支

   * `git branch -d feat/add-cli-export`
3. （可选）删除远端分支

   * `git push origin --delete feat/add-cli-export`

> 目标：main 永远保持可发布、可回滚、历史清晰。

---

### F. 维护者日常：每天固定 10–15 分钟处理 GitHub

除了写代码，你每天最好做这些维护动作：

1. **Triaging Issues**

   * 打标签：`bug`, `enhancement`, `docs`, `good first issue`
   * 明确复现步骤/期望行为
2. **PR 管理**

   * review / request changes
   * 合并后更新 release notes
3. **Release（按节奏）**

   * 版本号（SemVer：`MAJOR.MINOR.PATCH`）
   * `CHANGELOG.md`
   * GitHub Release
4. **仓库卫生**

   * `README`、`CONTRIBUTING`、`LICENSE`
   * `CODEOWNERS`（如果需要）
   * Issue/PR 模板

---

### G. 出错/救急：你最常用的“撤销工具箱”

* 撤销工作区改动：`git restore <file>`
* 撤销暂存：`git restore --staged <file>`
* 改上一次提交信息/补漏文件：`git commit --amend`
* 回滚一个提交（安全、开源友好）：`git revert <sha>`
* 本地“强力回退”（慎用，避免已 push 的提交）：`git reset --hard <sha>`

---

The end

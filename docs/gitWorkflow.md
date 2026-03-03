# Git Workflow Guide

---

## 🌿 Branch Naming Convention

```
<type>/<short-description>
```

| Type | Use for |
|------|---------|
| `feature/` | New features |
| `fix/` | Bug fixes |
| `hotfix/` | Urgent production fixes |
| `chore/` | Maintenance / config changes |
| `docs/` | Documentation updates |

**Examples:**
```
feature/user-authentication
fix/login-button-crash
docs/update-readme
```
 
---

## 🚀 Create & Push a Branch

```bash
# Create and switch to a new branch
git checkout -b feature/your-feature-name

# Push the branch to remote
git push -u origin feature/your-feature-name
```

---

## ✅ Commit Convention

Follow the **Conventional Commits** standard:

```
<type>(optional scope): <short description>
```

| Type | Use for |
|------|---------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation changes |
| `style` | Formatting, missing semicolons, etc. |
| `refactor` | Code refactor without feature/fix |
| `chore` | Build process or tooling changes |
| `test` | Adding or updating tests |

**Examples:**
```
feat(auth): add JWT login support
fix(cart): resolve item duplication bug
docs: update API usage in README
```

---

## 📤 Stage, Commit & Push

```bash
# Stage your changes
git add .

# Commit with a message
git commit -m "feat(scope): your message here"

# Push to your branch
git push
```

---

## 🔀 Merge Branch

```bash
# Switch to the target branch (usually main or develop)
git checkout main

# Pull latest changes
git pull origin main

# Merge your feature branch
git merge feature/your-feature-name

# Push the merged result
git push origin main
```

> 💡 **Tip:** Prefer opening a **Pull Request (PR)** on GitHub/GitLab instead of merging locally for code review.

---

## 🧹 Clean Up After Merge

```bash
# Delete local branch
git branch -d feature/your-feature-name

# Delete remote branch
git push origin --delete feature/your-feature-name
```
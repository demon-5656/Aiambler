#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_LINE 1024
#define MAX_ROWS 16
#define MAX_FIELDS 8
#define MAX_FIELD_NAME 32
#define MAX_FIELD_VALUE 96
#define MAX_GROUPS 8
#define MAX_GROUP_KEY 80
#define MAX_VARS 8
#define MAX_VAR_NAME 32
#define MAX_PIPE 16
#define MAX_OUTPUT 8192

typedef enum {
    VALUE_NONE = 0,
    VALUE_ROWS,
    VALUE_GROUPS,
    VALUE_TEXT
} ValueType;

typedef struct {
    char key[MAX_FIELD_NAME];
    char value[MAX_FIELD_VALUE];
} Field;

typedef struct {
    Field fields[MAX_FIELDS];
    int count;
} Row;

typedef struct {
    char key[MAX_GROUP_KEY];
    Row rows[MAX_ROWS];
    int row_count;
} Group;

typedef struct {
    ValueType type;
    Row rows[MAX_ROWS];
    int row_count;
    Group groups[MAX_GROUPS];
    int group_count;
    char text[MAX_OUTPUT];
} Value;

typedef struct {
    char name[MAX_VAR_NAME];
    Value value;
} Variable;

typedef struct {
    int b24_mode;
    int gm_mode;
    int dry;
    Variable vars[MAX_VARS];
    int var_count;
} Runtime;

static const Row TASKS[] = {
    {{{"id", "101"}, {"title", "Проверить гарантию"}, {"resp", "15"}, {"status", "open"}, {"project", "Проект 1"}, {"deadline", "2026-06-30"}, {"risk", "low"}}, 7},
    {{{"id", "102"}, {"title", "Согласовать отгрузку"}, {"resp", "15"}, {"status", "open"}, {"project", "Проект 2"}, {"deadline", "2026-06-28"}, {"risk", "medium"}}, 7},
    {{{"id", "103"}, {"title", "Закрыть архив"}, {"resp", "11"}, {"status", "closed"}, {"project", "Проект 1"}, {"deadline", "2026-05-01"}, {"risk", "low"}}, 7},
};

static const Row MAILS[] = {
    {{{"id", "m1"}, {"from", "client"}, {"body", "Нужен дедлайн до пятницы"}, {"deadline", "2026-06-26"}}, 4},
    {{{"id", "m2"}, {"from", "client"}, {"body", "Спасибо, без задач"}, {"deadline", ""}}, 4},
    {{{"id", "m3"}, {"from", "vendor"}, {"body", "Счет во вложении"}, {"deadline", ""}}, 4},
};

static char *trim(char *s) {
    while (isspace((unsigned char)*s)) {
        s++;
    }
    if (*s == '\0') {
        return s;
    }
    char *end = s + strlen(s) - 1;
    while (end > s && isspace((unsigned char)*end)) {
        *end = '\0';
        end--;
    }
    return s;
}

static void strip_comment(char *s) {
    int quote = 0;
    char *start = s;
    for (; *s; s++) {
        if ((*s == '"' || *s == '\'') && (s == start || s[-1] != '\\')) {
            quote = quote == 0 ? *s : (quote == *s ? 0 : quote);
        }
        if (*s == '#' && quote == 0) {
            *s = '\0';
            return;
        }
    }
}

static void value_clear(Value *value) {
    memset(value, 0, sizeof(*value));
    value->type = VALUE_NONE;
}

static const char *row_get(const Row *row, const char *key) {
    for (int i = 0; i < row->count; i++) {
        if (strcmp(row->fields[i].key, key) == 0) {
            return row->fields[i].value;
        }
    }
    return NULL;
}

static void row_set(Row *row, const char *key, const char *value) {
    for (int i = 0; i < row->count; i++) {
        if (strcmp(row->fields[i].key, key) == 0) {
            snprintf(row->fields[i].value, sizeof(row->fields[i].value), "%s", value);
            return;
        }
    }
    if (row->count < MAX_FIELDS) {
        snprintf(row->fields[row->count].key, sizeof(row->fields[row->count].key), "%s", key);
        snprintf(row->fields[row->count].value, sizeof(row->fields[row->count].value), "%s", value);
        row->count++;
    }
}

static int mode_from_text(const char *text) {
    if (strcmp(text, "ro") == 0) {
        return 1;
    }
    if (strcmp(text, "rw") == 0) {
        return 2;
    }
    if (strcmp(text, "admin") == 0) {
        return 3;
    }
    return 0;
}

static int ensure_read(Runtime *rt, const char *system, int line) {
    int mode = strcmp(system, "gm") == 0 ? rt->gm_mode : rt->b24_mode;
    if (mode < 1) {
        fprintf(stderr, "ERR_ACCESS_DENIED\nline: %d\nreason: system %s is not connected\n", line, system);
        return 0;
    }
    return 1;
}

static int ensure_write(Runtime *rt, const char *system, const char *cmd, int line) {
    int mode = strcmp(system, "gm") == 0 ? rt->gm_mode : rt->b24_mode;
    if (mode < 2) {
        fprintf(stderr, "ERR_ACCESS_DENIED\nline: %d\ncmd: %s\nreason: current mode is ro, but action requires rw\n", line, cmd);
        return 0;
    }
    return 1;
}

static int parse_params(char *text, Row *params) {
    params->count = 0;
    char *token = strtok(text, " \t");
    while (token != NULL) {
        char *colon = strchr(token, ':');
        if (colon == NULL) {
            return 0;
        }
        *colon = '\0';
        char *key = trim(token);
        char *value = trim(colon + 1);
        if (*value == '"' || *value == '\'') {
            char quote = *value++;
            size_t len = strlen(value);
            if (len > 0 && value[len - 1] == quote) {
                value[len - 1] = '\0';
            }
        }
        row_set(params, key, value);
        token = strtok(NULL, " \t");
    }
    return 1;
}

static int row_matches(const Row *row, const Row *params) {
    for (int i = 0; i < params->count; i++) {
        if (strcmp(params->fields[i].key, "after") == 0) {
            continue;
        }
        const char *actual = row_get(row, params->fields[i].key);
        if (actual == NULL || strcmp(actual, params->fields[i].value) != 0) {
            return 0;
        }
    }
    return 1;
}

static void value_add_row(Value *value, const Row *row) {
    if (value->row_count < MAX_ROWS) {
        value->rows[value->row_count++] = *row;
    }
}

static int run_query(Runtime *rt, char *expr, int line, Value *out) {
    char *question = strchr(expr, '?');
    if (question == NULL) {
        return 0;
    }
    *question = '\0';
    char *entity = trim(expr);
    char *params_text = trim(question + 1);
    Row params;
    if (!parse_params(params_text, &params)) {
        fprintf(stderr, "ERR_PARSE\nline: %d\nreason: bad query params\n", line);
        return 0;
    }

    value_clear(out);
    out->type = VALUE_ROWS;
    if (strcmp(entity, "task") == 0) {
        if (!ensure_read(rt, "b24", line)) {
            return 0;
        }
        for (size_t i = 0; i < sizeof(TASKS) / sizeof(TASKS[0]); i++) {
            if (row_matches(&TASKS[i], &params)) {
                value_add_row(out, &TASKS[i]);
            }
        }
        return 1;
    }
    if (strcmp(entity, "mail") == 0) {
        if (!ensure_read(rt, "gm", line)) {
            return 0;
        }
        for (size_t i = 0; i < sizeof(MAILS) / sizeof(MAILS[0]); i++) {
            if (row_matches(&MAILS[i], &params)) {
                value_add_row(out, &MAILS[i]);
            }
        }
        return 1;
    }
    fprintf(stderr, "ERR_UNKNOWN_COMMAND\nline: %d\nreason: unknown entity %s\n", line, entity);
    return 0;
}

static Variable *find_var(Runtime *rt, const char *name) {
    for (int i = 0; i < rt->var_count; i++) {
        if (strcmp(rt->vars[i].name, name) == 0) {
            return &rt->vars[i];
        }
    }
    return NULL;
}

static int save_var(Runtime *rt, const char *name, const Value *value) {
    Variable *var = find_var(rt, name);
    if (var == NULL) {
        if (rt->var_count >= MAX_VARS) {
            return 0;
        }
        var = &rt->vars[rt->var_count++];
        snprintf(var->name, sizeof(var->name), "%s", name);
    }
    var->value = *value;
    return 1;
}

static int load_var(Runtime *rt, const char *name, Value *out, int line) {
    Variable *var = find_var(rt, name);
    if (var == NULL) {
        fprintf(stderr, "ERR_RUNTIME\nline: %d\nreason: unknown variable %s\n", line, name);
        return 0;
    }
    *out = var->value;
    return 1;
}

static int apply_group(Value *value, const char *field, int line) {
    if (value->type != VALUE_ROWS) {
        fprintf(stderr, "ERR_RUNTIME\nline: %d\nreason: group requires rows\n", line);
        return 0;
    }
    Value grouped;
    value_clear(&grouped);
    grouped.type = VALUE_GROUPS;
    for (int i = 0; i < value->row_count; i++) {
        const char *key = row_get(&value->rows[i], field);
        if (key == NULL) {
            fprintf(stderr, "ERR_UNKNOWN_FIELD\nline: %d\nfield: %s\n", line, field);
            return 0;
        }
        int group_idx = -1;
        for (int g = 0; g < grouped.group_count; g++) {
            if (strcmp(grouped.groups[g].key, key) == 0) {
                group_idx = g;
                break;
            }
        }
        if (group_idx < 0) {
            if (grouped.group_count >= MAX_GROUPS) {
                fprintf(stderr, "ERR_RUNTIME\nline: %d\nreason: too many groups\n", line);
                return 0;
            }
            group_idx = grouped.group_count++;
            snprintf(grouped.groups[group_idx].key, sizeof(grouped.groups[group_idx].key), "%s", key);
        }
        Group *group = &grouped.groups[group_idx];
        if (group->row_count < MAX_ROWS) {
            group->rows[group->row_count++] = value->rows[i];
        }
    }
    *value = grouped;
    return 1;
}

static void project_row(Row *row, char fields[][MAX_FIELD_NAME], int field_count) {
    Row projected;
    projected.count = 0;
    for (int i = 0; i < field_count; i++) {
        const char *v = row_get(row, fields[i]);
        row_set(&projected, fields[i], v == NULL ? "" : v);
    }
    *row = projected;
}

static int parse_csv_fields(char *text, char fields[][MAX_FIELD_NAME], int *field_count) {
    *field_count = 0;
    char *token = strtok(text, ",");
    while (token != NULL) {
        if (*field_count >= MAX_FIELDS) {
            return 0;
        }
        snprintf(fields[*field_count], MAX_FIELD_NAME, "%s", trim(token));
        (*field_count)++;
        token = strtok(NULL, ",");
    }
    return 1;
}

static int apply_sum(Value *value, char *args) {
    char fields[MAX_FIELDS][MAX_FIELD_NAME];
    int field_count = 0;
    if (!parse_csv_fields(args, fields, &field_count)) {
        return 0;
    }
    if (value->type == VALUE_ROWS) {
        for (int i = 0; i < value->row_count; i++) {
            project_row(&value->rows[i], fields, field_count);
        }
        return 1;
    }
    if (value->type == VALUE_GROUPS) {
        for (int g = 0; g < value->group_count; g++) {
            for (int r = 0; r < value->groups[g].row_count; r++) {
                project_row(&value->groups[g].rows[r], fields, field_count);
            }
        }
        return 1;
    }
    return 0;
}

static int apply_has(Value *value, const char *field) {
    if (value->type != VALUE_ROWS) {
        return 0;
    }
    int write = 0;
    for (int i = 0; i < value->row_count; i++) {
        const char *v = row_get(&value->rows[i], field);
        if (v != NULL && *v != '\0') {
            value->rows[write++] = value->rows[i];
        }
    }
    value->row_count = write;
    return 1;
}

static void append_text(char *buf, size_t size, const char *text) {
    size_t used = strlen(buf);
    if (used < size - 1) {
        snprintf(buf + used, size - used, "%s", text);
    }
}

static int apply_out_md(Value *value) {
    char out[MAX_OUTPUT];
    out[0] = '\0';
    if (value->type == VALUE_GROUPS) {
        for (int g = 0; g < value->group_count; g++) {
            append_text(out, sizeof(out), value->groups[g].key);
            append_text(out, sizeof(out), ":\n");
            for (int r = 0; r < value->groups[g].row_count; r++) {
                append_text(out, sizeof(out), "- ");
                for (int f = 0; f < value->groups[g].rows[r].count; f++) {
                    if (f > 0) {
                        append_text(out, sizeof(out), "; ");
                    }
                    append_text(out, sizeof(out), value->groups[g].rows[r].fields[f].key);
                    append_text(out, sizeof(out), ": ");
                    append_text(out, sizeof(out), value->groups[g].rows[r].fields[f].value);
                }
                append_text(out, sizeof(out), "\n");
            }
            append_text(out, sizeof(out), "\n");
        }
    } else if (value->type == VALUE_ROWS) {
        for (int r = 0; r < value->row_count; r++) {
            append_text(out, sizeof(out), "- ");
            for (int f = 0; f < value->rows[r].count; f++) {
                if (f > 0) {
                    append_text(out, sizeof(out), "; ");
                }
                append_text(out, sizeof(out), value->rows[r].fields[f].key);
                append_text(out, sizeof(out), ": ");
                append_text(out, sizeof(out), value->rows[r].fields[f].value);
            }
            append_text(out, sizeof(out), "\n");
        }
    }
    value_clear(value);
    value->type = VALUE_TEXT;
    snprintf(value->text, sizeof(value->text), "%s", out);
    printf("%s", value->text);
    return 1;
}

static int run_update(Runtime *rt, char *expr, int line, Value *out) {
    char cmd[MAX_LINE];
    snprintf(cmd, sizeof(cmd), "%s", expr);
    char *params_text = strchr(expr, ' ');
    if (params_text == NULL) {
        params_text = "";
    } else {
        *params_text++ = '\0';
    }
    if (!ensure_write(rt, "b24", "b24.task.update", line)) {
        return 0;
    }
    Row params;
    if (!parse_params(params_text, &params)) {
        fprintf(stderr, "ERR_PARSE\nline: %d\nreason: bad command params\n", line);
        return 0;
    }
    value_clear(out);
    out->type = VALUE_TEXT;
    const char *id = row_get(&params, "id");
    const char *stage = row_get(&params, "stage");
    if (rt->dry) {
        snprintf(out->text, sizeof(out->text),
                 "dry_run: true\naction: update\nentity: task\nid: %s\nstage: %s\nrisk: write\nrequires_confirmation: true\n",
                 id == NULL ? "" : id, stage == NULL ? "" : stage);
    } else {
        snprintf(out->text, sizeof(out->text), "ok: true\naction: update\nentity: task\nid: %s\n", id == NULL ? "" : id);
    }
    printf("%s", out->text);
    (void)cmd;
    return 1;
}

static int run_create_from_rows(Runtime *rt, Value *value, int line) {
    if (!ensure_write(rt, "b24", "b24.task.create", line)) {
        return 0;
    }
    if (value->type != VALUE_ROWS) {
        fprintf(stderr, "ERR_RUNTIME\nline: %d\nreason: create pipe requires rows\n", line);
        return 0;
    }
    for (int i = 0; i < value->row_count; i++) {
        const char *id = row_get(&value->rows[i], "id");
        if (rt->dry) {
            printf("dry_run: true\naction: create\nentity: task\nsource_id: %s\nrisk: write\nrequires_confirmation: true\n", id == NULL ? "" : id);
        } else {
            printf("ok: true\naction: create\nentity: task\nsource_id: %s\n", id == NULL ? "" : id);
        }
    }
    return 1;
}

static int eval_atom(Runtime *rt, char *atom, int line, Value *out) {
    atom = trim(atom);
    if (strchr(atom, '?') != NULL) {
        return run_query(rt, atom, line, out);
    }
    if (strncmp(atom, "b24.task.update", 15) == 0) {
        return run_update(rt, atom, line, out);
    }
    return load_var(rt, atom, out, line);
}

static int apply_step(Runtime *rt, Value *value, char *step, int line) {
    step = trim(step);
    if (strncmp(step, "group(", 6) == 0) {
        char *arg = step + 6;
        char *end = strrchr(arg, ')');
        if (end != NULL) {
            *end = '\0';
        }
        return apply_group(value, trim(arg), line);
    }
    if (strncmp(step, "sum(", 4) == 0) {
        char *arg = step + 4;
        char *end = strrchr(arg, ')');
        if (end != NULL) {
            *end = '\0';
        }
        return apply_sum(value, arg);
    }
    if (strncmp(step, "has(", 4) == 0) {
        char *arg = step + 4;
        char *end = strrchr(arg, ')');
        if (end != NULL) {
            *end = '\0';
        }
        return apply_has(value, trim(arg));
    }
    if (strcmp(step, "out.md") == 0) {
        return apply_out_md(value);
    }
    if (strcmp(step, "b24.task+") == 0) {
        return run_create_from_rows(rt, value, line);
    }
    fprintf(stderr, "ERR_UNKNOWN_COMMAND\nline: %d\ncmd: %s\n", line, step);
    return 0;
}

static int eval_expr(Runtime *rt, char *expr, int line, Value *out) {
    char *parts[MAX_PIPE];
    int part_count = 0;
    char *cursor = expr;
    while (part_count < MAX_PIPE) {
        char *pipe = strstr(cursor, "|>");
        if (pipe == NULL) {
            parts[part_count++] = trim(cursor);
            break;
        }
        *pipe = '\0';
        parts[part_count++] = trim(cursor);
        cursor = pipe + 2;
    }
    if (part_count == 0) {
        value_clear(out);
        return 1;
    }
    if (!eval_atom(rt, parts[0], line, out)) {
        return 0;
    }
    for (int i = 1; i < part_count; i++) {
        if (!apply_step(rt, out, parts[i], line)) {
            return 0;
        }
    }
    return 1;
}

static int run_line(Runtime *rt, char *line, int line_no) {
    strip_comment(line);
    line = trim(line);
    if (*line == '\0') {
        return 1;
    }
    if (strncmp(line, "use ", 4) == 0) {
        char system[32];
        char mode[32];
        if (sscanf(line, "use %31s %31s", system, mode) != 2) {
            fprintf(stderr, "ERR_PARSE\nline: %d\nreason: bad use statement\n", line_no);
            return 0;
        }
        int parsed = mode_from_text(mode);
        if (parsed == 0) {
            fprintf(stderr, "ERR_PARSE\nline: %d\nreason: unknown mode %s\n", line_no, mode);
            return 0;
        }
        if (strcmp(system, "gm") == 0 || strcmp(system, "gmail") == 0) {
            rt->gm_mode = parsed;
        } else if (strcmp(system, "b24") == 0 || strcmp(system, "bitrix") == 0 || strcmp(system, "bitrix24") == 0) {
            rt->b24_mode = parsed;
        } else {
            fprintf(stderr, "ERR_UNKNOWN_COMMAND\nline: %d\nreason: unknown system %s\n", line_no, system);
            return 0;
        }
        return 1;
    }
    if (strcmp(line, "dry") == 0) {
        rt->dry = 1;
        return 1;
    }

    char *eq = strchr(line, '=');
    if (eq != NULL) {
        *eq = '\0';
        char *name = trim(line);
        char *expr = trim(eq + 1);
        Value value;
        if (!eval_expr(rt, expr, line_no, &value)) {
            return 0;
        }
        if (!save_var(rt, name, &value)) {
            fprintf(stderr, "ERR_RUNTIME\nline: %d\nreason: too many variables\n", line_no);
            return 0;
        }
        return 1;
    }

    Value value;
    return eval_expr(rt, line, line_no, &value);
}

static int run_file(const char *path) {
    FILE *file = fopen(path, "r");
    if (file == NULL) {
        perror(path);
        return 1;
    }
    Runtime rt;
    memset(&rt, 0, sizeof(rt));
    char line[MAX_LINE];
    int line_no = 0;
    while (fgets(line, sizeof(line), file) != NULL) {
        line_no++;
        if (!run_line(&rt, line, line_no)) {
            fclose(file);
            return 1;
        }
    }
    fclose(file);
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s script.ai\n", argv[0]);
        return 2;
    }
    return run_file(argv[1]);
}

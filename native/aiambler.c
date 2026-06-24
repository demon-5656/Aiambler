#include <ctype.h>
#include <pthread.h>
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
    VALUE_NUM,
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
    double num;
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
    int jobs;
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

static void value_set_num(Value *value, double num) {
    value_clear(value);
    value->type = VALUE_NUM;
    value->num = num;
}

static void value_set_text(Value *value, const char *text) {
    value_clear(value);
    value->type = VALUE_TEXT;
    snprintf(value->text, sizeof(value->text), "%s", text);
}

static void print_num(double num) {
    if (num == (long long)num) {
        printf("%lld\n", (long long)num);
    } else {
        printf("%.10g\n", num);
    }
}

static void append_text(char *buf, size_t size, const char *text);

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

typedef struct {
    Runtime *rt;
    const char *s;
    int line;
    int ok;
} MathParser;

static void math_skip_ws(MathParser *p) {
    while (isspace((unsigned char)*p->s)) {
        p->s++;
    }
}

static double parse_math_expr(MathParser *p);

static double var_number(Runtime *rt, const char *name, int line, int *ok) {
    Variable *var = find_var(rt, name);
    if (var == NULL || var->value.type != VALUE_NUM) {
        fprintf(stderr, "ERR_RUNTIME\nline: %d\nreason: unknown numeric variable %s\n", line, name);
        *ok = 0;
        return 0.0;
    }
    return var->value.num;
}

static double parse_math_factor(MathParser *p) {
    math_skip_ws(p);
    if (*p->s == '(') {
        p->s++;
        double value = parse_math_expr(p);
        math_skip_ws(p);
        if (*p->s != ')') {
            fprintf(stderr, "ERR_PARSE\nline: %d\nreason: expected )\n", p->line);
            p->ok = 0;
            return 0.0;
        }
        p->s++;
        return value;
    }
    if (*p->s == '-') {
        p->s++;
        return -parse_math_factor(p);
    }
    if (isdigit((unsigned char)*p->s) || *p->s == '.') {
        char *end = NULL;
        double value = strtod(p->s, &end);
        if (end == p->s) {
            p->ok = 0;
            return 0.0;
        }
        p->s = end;
        return value;
    }
    if (isalpha((unsigned char)*p->s) || *p->s == '_') {
        char name[MAX_VAR_NAME];
        int i = 0;
        while ((isalnum((unsigned char)*p->s) || *p->s == '_') && i < MAX_VAR_NAME - 1) {
            name[i++] = *p->s++;
        }
        name[i] = '\0';
        return var_number(p->rt, name, p->line, &p->ok);
    }
    fprintf(stderr, "ERR_PARSE\nline: %d\nreason: bad math factor\n", p->line);
    p->ok = 0;
    return 0.0;
}

static double parse_math_term(MathParser *p) {
    double value = parse_math_factor(p);
    while (p->ok) {
        math_skip_ws(p);
        if (*p->s == '*') {
            p->s++;
            value *= parse_math_factor(p);
        } else if (*p->s == '/') {
            p->s++;
            double rhs = parse_math_factor(p);
            if (rhs == 0.0) {
                fprintf(stderr, "ERR_RUNTIME\nline: %d\nreason: division by zero\n", p->line);
                p->ok = 0;
                return 0.0;
            }
            value /= rhs;
        } else {
            break;
        }
    }
    return value;
}

static double parse_math_expr(MathParser *p) {
    double value = parse_math_term(p);
    while (p->ok) {
        math_skip_ws(p);
        if (*p->s == '+') {
            p->s++;
            value += parse_math_term(p);
        } else if (*p->s == '-') {
            p->s++;
            value -= parse_math_term(p);
        } else {
            break;
        }
    }
    return value;
}

static int looks_like_math(const char *s) {
    int has_digit = 0;
    int has_op = 0;
    for (; *s; s++) {
        if (isdigit((unsigned char)*s)) {
            has_digit = 1;
        }
        if (*s == '+' || *s == '*' || *s == '/' || *s == '(' || *s == ')') {
            has_op = 1;
        }
        if (*s == '-' && isspace((unsigned char)s[1])) {
            has_op = 1;
        }
    }
    return has_digit || has_op;
}

static int eval_math(Runtime *rt, const char *expr, int line, Value *out) {
    MathParser parser;
    parser.rt = rt;
    parser.s = expr;
    parser.line = line;
    parser.ok = 1;
    double value = parse_math_expr(&parser);
    math_skip_ws(&parser);
    if (!parser.ok || *parser.s != '\0') {
        if (parser.ok) {
            fprintf(stderr, "ERR_PARSE\nline: %d\nreason: trailing math input near %s\n", line, parser.s);
        }
        return 0;
    }
    value_set_num(out, value);
    return 1;
}

typedef struct {
    unsigned long long start;
    unsigned long long end;
    double result;
} FpJob;

static double fp_kernel(unsigned long long i) {
    double x = (double)(i % 1009) * 0.0009910802775024777;
    double y = (double)((i * 17ULL + 13ULL) % 997) * 0.0010030090270812437;
    for (int k = 0; k < 8; k++) {
        x = x * 1.000000119 + y * 0.999999937 + 0.000001;
        y = y * 0.999999911 + x * 0.000000173 + 0.000002;
    }
    return x * y + x / (y + 1.0);
}

static void *fp_worker(void *arg) {
    FpJob *job = (FpJob *)arg;
    double acc = 0.0;
    for (unsigned long long i = job->start; i < job->end; i++) {
        acc += fp_kernel(i);
    }
    job->result = acc;
    return NULL;
}

static int run_fp(Runtime *rt, char *expr, int line, Value *out) {
    char *arg = expr + 3;
    char *end = strrchr(arg, ')');
    if (end != NULL) {
        *end = '\0';
    }
    unsigned long long n = strtoull(trim(arg), NULL, 10);
    if (n == 0) {
        fprintf(stderr, "ERR_PARSE\nline: %d\nreason: fp requires positive iteration count\n", line);
        return 0;
    }
    int jobs = rt->jobs < 1 ? 1 : rt->jobs;
    if ((unsigned long long)jobs > n) {
        jobs = (int)n;
    }
    FpJob *work = (FpJob *)calloc((size_t)jobs, sizeof(FpJob));
    pthread_t *threads = (pthread_t *)calloc((size_t)jobs, sizeof(pthread_t));
    if (work == NULL || threads == NULL) {
        free(work);
        free(threads);
        fprintf(stderr, "ERR_RUNTIME\nline: %d\nreason: allocation failed\n", line);
        return 0;
    }
    unsigned long long chunk = n / (unsigned long long)jobs;
    unsigned long long rem = n % (unsigned long long)jobs;
    unsigned long long cursor = 0;
    for (int j = 0; j < jobs; j++) {
        unsigned long long len = chunk + ((unsigned long long)j < rem ? 1ULL : 0ULL);
        work[j].start = cursor;
        work[j].end = cursor + len;
        cursor += len;
        if (jobs == 1) {
            fp_worker(&work[j]);
        } else if (pthread_create(&threads[j], NULL, fp_worker, &work[j]) != 0) {
            free(work);
            free(threads);
            fprintf(stderr, "ERR_RUNTIME\nline: %d\nreason: pthread_create failed\n", line);
            return 0;
        }
    }
    double total = 0.0;
    for (int j = 0; j < jobs; j++) {
        if (jobs > 1) {
            pthread_join(threads[j], NULL);
        }
        total += work[j].result;
    }
    free(work);
    free(threads);
    value_set_num(out, total);
    return 1;
}

typedef struct {
    const double *a;
    const double *b;
    double *c;
    int n;
    int row_start;
    int row_end;
} MatJob;

static void *matmul_worker(void *arg) {
    MatJob *job = (MatJob *)arg;
    int n = job->n;
    for (int i = job->row_start; i < job->row_end; i++) {
        for (int k = 0; k < n; k++) {
            double aik = job->a[(size_t)i * (size_t)n + (size_t)k];
            for (int j = 0; j < n; j++) {
                job->c[(size_t)i * (size_t)n + (size_t)j] += aik * job->b[(size_t)k * (size_t)n + (size_t)j];
            }
        }
    }
    return NULL;
}

static int run_matmul(Runtime *rt, char *expr, int line, Value *out) {
    char *arg = expr + 3;
    char *end = strrchr(arg, ')');
    if (end != NULL) {
        *end = '\0';
    }
    int n = atoi(trim(arg));
    if (n <= 0 || n > 2048) {
        fprintf(stderr, "ERR_PARSE\nline: %d\nreason: mm requires size 1..2048\n", line);
        return 0;
    }
    size_t cells = (size_t)n * (size_t)n;
    double *a = (double *)malloc(cells * sizeof(double));
    double *b = (double *)malloc(cells * sizeof(double));
    double *c = (double *)calloc(cells, sizeof(double));
    if (a == NULL || b == NULL || c == NULL) {
        free(a);
        free(b);
        free(c);
        fprintf(stderr, "ERR_RUNTIME\nline: %d\nreason: allocation failed\n", line);
        return 0;
    }
    for (size_t i = 0; i < cells; i++) {
        a[i] = (double)((i * 13U + 7U) % 101U) * 0.01;
        b[i] = (double)((i * 17U + 3U) % 97U) * 0.01;
    }

    int jobs = rt->jobs < 1 ? 1 : rt->jobs;
    if (jobs > n) {
        jobs = n;
    }
    MatJob *work = (MatJob *)calloc((size_t)jobs, sizeof(MatJob));
    pthread_t *threads = (pthread_t *)calloc((size_t)jobs, sizeof(pthread_t));
    if (work == NULL || threads == NULL) {
        free(a);
        free(b);
        free(c);
        free(work);
        free(threads);
        fprintf(stderr, "ERR_RUNTIME\nline: %d\nreason: allocation failed\n", line);
        return 0;
    }
    int rows = n / jobs;
    int rem = n % jobs;
    int row = 0;
    for (int j = 0; j < jobs; j++) {
        int len = rows + (j < rem ? 1 : 0);
        work[j].a = a;
        work[j].b = b;
        work[j].c = c;
        work[j].n = n;
        work[j].row_start = row;
        work[j].row_end = row + len;
        row += len;
        if (jobs == 1) {
            matmul_worker(&work[j]);
        } else if (pthread_create(&threads[j], NULL, matmul_worker, &work[j]) != 0) {
            free(a);
            free(b);
            free(c);
            free(work);
            free(threads);
            fprintf(stderr, "ERR_RUNTIME\nline: %d\nreason: pthread_create failed\n", line);
            return 0;
        }
    }
    for (int j = 0; j < jobs; j++) {
        if (jobs > 1) {
            pthread_join(threads[j], NULL);
        }
    }

    double checksum = 0.0;
    for (size_t i = 0; i < cells; i++) {
        checksum += c[i];
    }
    free(a);
    free(b);
    free(c);
    free(work);
    free(threads);
    value_set_num(out, checksum);
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

static int run_file_read(char *expr, int line, Value *out) {
    char *path = trim(expr + 9);
    if (*path == '"' || *path == '\'') {
        char quote = *path++;
        size_t len = strlen(path);
        if (len > 0 && path[len - 1] == quote) {
            path[len - 1] = '\0';
        }
    }
    FILE *file = fopen(path, "r");
    if (file == NULL) {
        fprintf(stderr, "ERR_FILE\nline: %d\nreason: cannot read %s\n", line, path);
        return 0;
    }
    value_clear(out);
    out->type = VALUE_TEXT;
    size_t n = fread(out->text, 1, sizeof(out->text) - 1, file);
    out->text[n] = '\0';
    fclose(file);
    return 1;
}

static int apply_grep(Value *value, const char *needle) {
    if (value->type != VALUE_TEXT) {
        return 0;
    }
    char src[MAX_OUTPUT];
    char out[MAX_OUTPUT];
    snprintf(src, sizeof(src), "%s", value->text);
    out[0] = '\0';
    char *line = strtok(src, "\n");
    while (line != NULL) {
        if (strstr(line, needle) != NULL) {
            append_text(out, sizeof(out), line);
            append_text(out, sizeof(out), "\n");
        }
        line = strtok(NULL, "\n");
    }
    value_set_text(value, out);
    return 1;
}

static int apply_nums(Value *value) {
    const char *src = NULL;
    char combined[MAX_OUTPUT];
    combined[0] = '\0';
    if (value->type == VALUE_TEXT) {
        src = value->text;
    } else if (value->type == VALUE_ROWS) {
        for (int r = 0; r < value->row_count; r++) {
            for (int f = 0; f < value->rows[r].count; f++) {
                append_text(combined, sizeof(combined), value->rows[r].fields[f].value);
                append_text(combined, sizeof(combined), " ");
            }
        }
        src = combined;
    } else {
        return 0;
    }

    Value rows;
    value_clear(&rows);
    rows.type = VALUE_ROWS;
    while (*src != '\0' && rows.row_count < MAX_ROWS) {
        if (isdigit((unsigned char)*src) || ((*src == '-' || *src == '+') && isdigit((unsigned char)src[1]))) {
            char *end = NULL;
            double number = strtod(src, &end);
            if (end != src) {
                char buf[64];
                snprintf(buf, sizeof(buf), "%.10g", number);
                Row row;
                row.count = 0;
                row_set(&row, "n", buf);
                value_add_row(&rows, &row);
                src = end;
                continue;
            }
        }
        src++;
    }
    *value = rows;
    return 1;
}

static int apply_numeric_sum(Value *value) {
    double total = 0.0;
    if (value->type == VALUE_NUM) {
        return 1;
    }
    if (value->type == VALUE_TEXT) {
        const char *src = value->text;
        while (*src != '\0') {
            if (isdigit((unsigned char)*src) || ((*src == '-' || *src == '+') && isdigit((unsigned char)src[1]))) {
                char *end = NULL;
                double number = strtod(src, &end);
                if (end != src) {
                    total += number;
                    src = end;
                    continue;
                }
            }
            src++;
        }
        value_set_num(value, total);
        return 1;
    }
    if (value->type == VALUE_ROWS) {
        for (int i = 0; i < value->row_count; i++) {
            const char *n = row_get(&value->rows[i], "n");
            if (n != NULL) {
                total += strtod(n, NULL);
            }
        }
        value_set_num(value, total);
        return 1;
    }
    return 0;
}

static int apply_count(Value *value) {
    int count = 0;
    if (value->type == VALUE_ROWS) {
        count = value->row_count;
    } else if (value->type == VALUE_GROUPS) {
        count = value->group_count;
    } else if (value->type == VALUE_TEXT) {
        for (char *p = value->text; *p; p++) {
            if (*p == '\n') {
                count++;
            }
        }
        if (value->text[0] != '\0' && value->text[strlen(value->text) - 1] != '\n') {
            count++;
        }
    } else if (value->type == VALUE_NUM) {
        count = 1;
    }
    value_set_num(value, (double)count);
    return 1;
}

static int apply_len(Value *value) {
    if (value->type != VALUE_TEXT) {
        return 0;
    }
    value_set_num(value, (double)strlen(value->text));
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
    } else if (value->type == VALUE_NUM) {
        print_num(value->num);
        return 1;
    } else if (value->type == VALUE_TEXT) {
        printf("%s", value->text);
        if (value->text[0] != '\0' && value->text[strlen(value->text) - 1] != '\n') {
            printf("\n");
        }
        return 1;
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
    if (strncmp(atom, "file.read ", 10) == 0) {
        return run_file_read(atom, line, out);
    }
    if (strncmp(atom, "fp(", 3) == 0) {
        return run_fp(rt, atom, line, out);
    }
    if (strncmp(atom, "mm(", 3) == 0) {
        return run_matmul(rt, atom, line, out);
    }
    if (strncmp(atom, "b24.task.update", 15) == 0) {
        return run_update(rt, atom, line, out);
    }
    if (*atom == '"' || *atom == '\'') {
        char quote = *atom++;
        size_t len = strlen(atom);
        if (len > 0 && atom[len - 1] == quote) {
            atom[len - 1] = '\0';
        }
        value_set_text(out, atom);
        return 1;
    }
    if (looks_like_math(atom)) {
        return eval_math(rt, atom, line, out);
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
        if (*trim(arg) == '\0') {
            return apply_numeric_sum(value);
        }
        return apply_sum(value, arg);
    }
    if (strcmp(step, "sum") == 0) {
        return apply_numeric_sum(value);
    }
    if (strcmp(step, "nums") == 0) {
        return apply_nums(value);
    }
    if (strncmp(step, "grep(", 5) == 0) {
        char *arg = step + 5;
        char *end = strrchr(arg, ')');
        if (end != NULL) {
            *end = '\0';
        }
        arg = trim(arg);
        if (*arg == '"' || *arg == '\'') {
            char quote = *arg++;
            size_t len = strlen(arg);
            if (len > 0 && arg[len - 1] == quote) {
                arg[len - 1] = '\0';
            }
        }
        return apply_grep(value, arg);
    }
    if (strcmp(step, "count") == 0) {
        return apply_count(value);
    }
    if (strcmp(step, "len") == 0) {
        return apply_len(value);
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
    if (strcmp(step, "out") == 0 || strcmp(step, "out.text") == 0) {
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

static int run_file(const char *path, int jobs) {
    FILE *file = fopen(path, "r");
    if (file == NULL) {
        perror(path);
        return 1;
    }
    Runtime rt;
    memset(&rt, 0, sizeof(rt));
    rt.jobs = jobs < 1 ? 1 : jobs;
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
    int jobs = 1;
    const char *script = NULL;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--jobs") == 0 || strcmp(argv[i], "-j") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "usage: %s [--jobs N] script.ai\n", argv[0]);
                return 2;
            }
            jobs = atoi(argv[++i]);
            if (jobs < 1) {
                jobs = 1;
            }
        } else {
            script = argv[i];
        }
    }
    if (script == NULL) {
        fprintf(stderr, "usage: %s [--jobs N] script.ai\n", argv[0]);
        return 2;
    }
    return run_file(script, jobs);
}

"""
Creating first migration
"""
from yoyo import step, group
group([
    step("CREATE TABLE IF NOT EXISTS public.product(id serial "
         "PRIMARY KEY NOT NULL, name text NOT NULL, key text NOT NULL);"),

    step("CREATE UNIQUE INDEX IF NOT EXISTS product_key_key ON public.product (key);"),

    step("CREATE TABLE IF NOT EXISTS public.team(id serial PRIMARY KEY NOT NULL,"
         "name text NOT NULL,product integer,CONSTRAINT fk_team__product FOREIGN KEY (product) "
         "REFERENCES product (id));"),

    step("CREATE TABLE IF NOT EXISTS public.staff(id serial PRIMARY KEY NOT NULL,"
         "first_name text NOT NULL,last_name text NOT NULL,company text NOT NULL,avatar_url text NOT NULL,"
         "role text NOT NULL,email text NOT NULL,rate double precision NOT NULL,start_date date NOT NULL,"
         "type text NOT NULL,jira_username text NOT NULL,github_username text NOT NULL,status text NOT NULL,"
         "base_daily_cost double precision,base_weekly_cost double precision,base_annual_cost double precision);"),

    step("CREATE TABLE IF NOT EXISTS public.toolissuetype(id serial PRIMARY KEY "
         "NOT NULL,tool_issue_type_name text NOT NULL,tool_issue_type_type text NOT NULL);"),

    step("CREATE TABLE IF NOT EXISTS public.toolproject(id serial "
         "PRIMARY KEY NOT NULL,tool_project_key text NOT NULL);"),

    step("CREATE TABLE IF NOT EXISTS public.toolprojectcategory(id serial "
         "PRIMARY KEY NOT NULL,tool_category_name text NOT NULL);"),

    step("CREATE TABLE IF NOT EXISTS public.toolissueresolution(id serial "
         "PRIMARY KEY NOT NULL,tool_issue_resolution_name text NOT NULL,tool_issue_resolution_type text NOT NULL);"),

    step("CREATE TABLE IF NOT EXISTS public.toolissuestatus(id serial "
         "PRIMARY KEY NOT NULL,tool_issue_status_name text NOT NULL,tool_issue_status_type text NOT NULL);"),

    step("CREATE TABLE IF NOT EXISTS public.workflowdefectprojectfilter(id serial PRIMARY KEY NOT NULL,"
         "project_key text NOT NULL);"),

    step("CREATE TABLE IF NOT EXISTS public.workflow(id serial "
         "PRIMARY KEY NOT NULL,name text NOT NULL);"),

    step("CREATE TABLE IF NOT EXISTS public.agileboard(id serial PRIMARY KEY "
         "NOT NULL,jira_id integer,team integer,CONSTRAINT fk_agileboard__team FOREIGN KEY (team) "
         "REFERENCES team (id));"),

    step("CREATE INDEX IF NOT EXISTS idx_agileboard__team ON public.agileboard (team);"),

    step("CREATE TABLE IF NOT EXISTS public.group(id serial PRIMARY KEY NOT NULL,"
         "name text NOT NULL,workflow integer,CONSTRAINT fk_group__workflow FOREIGN KEY (workflow) "
         "REFERENCES workflow (id))"),

    step("CREATE INDEX IF NOT EXISTS idx_group__workflow ON public.group (workflow);"),

    step("CREATE TABLE IF NOT EXISTS public.group_product(\"group\" integer NOT NULL,"
         "product integer NOT NULL,CONSTRAINT "
         "group_product_pkey PRIMARY KEY (\"group\", product),CONSTRAINT fk_group_product__group FOREIGN KEY "
         "(\"group\") REFERENCES \"group\" (id),CONSTRAINT fk_group_product__product FOREIGN KEY (product) "
         "REFERENCES product (id));"),

    step("CREATE INDEX IF NOT EXISTS idx_group_product ON public.group_product (product);"),

    step("CREATE TABLE IF NOT EXISTS public.group_team(\"group\" integer NOT NULL, team integer NOT NULL, CONSTRAINT "
         "group_team_pkey PRIMARY KEY (\"group\", team), CONSTRAINT fk_group_team__group FOREIGN KEY (\"group\") "
         "REFERENCES \"group\" (id), CONSTRAINT fk_group_team__team FOREIGN KEY (team) REFERENCES team (id));"),

    step("CREATE INDEX IF NOT EXISTS idx_group_team ON public.group_team (team);"),


    step("CREATE TABLE IF NOT EXISTS public.staff_team(staff integer NOT NULL,team "
         "integer NOT NULL,CONSTRAINT staff_team_pkey "
         "PRIMARY KEY (staff, team),CONSTRAINT fk_staff_team__staff FOREIGN KEY (staff) REFERENCES staff (id),"
         "CONSTRAINT fk_staff_team__team FOREIGN KEY (team) REFERENCES team (id));"),

    step("CREATE INDEX IF NOT EXISTS idx_staff_team ON public.staff_team (team);"),

    step("CREATE INDEX IF NOT EXISTS idx_team__product ON public.team (product);"),

    step("CREATE TABLE IF NOT EXISTS public.toolissueresolution_workflow(toolissueresolution integer NOT NULL,"
         "workflow integer NOT NULL,CONSTRAINT toolissueresolution_workflow_pkey PRIMARY KEY "
         "(toolissueresolution, workflow),CONSTRAINT fk_toolissueresolution_workflow__toolissueresolution "
         "FOREIGN KEY (toolissueresolution) REFERENCES toolissueresolution (id),"
         "CONSTRAINT fk_toolissueresolution_workflow__workflow FOREIGN KEY (workflow) REFERENCES workflow (id));"),

    step("CREATE INDEX IF NOT EXISTS idx_toolissueresolution_workflow ON "
         "public.toolissueresolution_workflow (workflow);"),

    step("CREATE TABLE IF NOT EXISTS public.toolissuestatus_workflow(toolissuestatus integer NOT NULL,"
         "workflow integer NOT NULL,"
         "CONSTRAINT toolissuestatus_workflow_pkey PRIMARY KEY (toolissuestatus, workflow),"
         "CONSTRAINT fk_toolissuestatus_workflow__toolissuestatus FOREIGN KEY (toolissuestatus) "
         "REFERENCES toolissuestatus (id),CONSTRAINT fk_toolissuestatus_workflow__workflow FOREIGN KEY (workflow) "
         "REFERENCES workflow (id));"),

    step("CREATE INDEX IF NOT EXISTS idx_toolissuestatus_workflow ON public.toolissuestatus_workflow (workflow);"),

    step("CREATE TABLE IF NOT EXISTS public.toolissuetype_workflow(toolissuetype integer NOT NULL,"
         "workflow integer NOT NULL,"
         "CONSTRAINT toolissuetype_workflow_pkey PRIMARY KEY (toolissuetype, workflow),"
         "CONSTRAINT fk_toolissuetype_workflow__toolissuetype FOREIGN KEY (toolissuetype) REFERENCES "
         "toolissuetype (id),CONSTRAINT fk_toolissuetype_workflow__workflow FOREIGN KEY (workflow) "
         "REFERENCES workflow (id));"),

    step("CREATE INDEX IF NOT EXISTS idx_toolissuetype_workflow ON public.toolissuetype_workflow (workflow);"),

    step("CREATE TABLE IF NOT EXISTS public.toolissuetype_workflowdefectprojectfilter(toolissuetype integer NOT NULL,"
         "workflowdefectprojectfilter integer NOT NULL,CONSTRAINT toolissuetype_workflowdefectprojectfilter_pkey "
         "PRIMARY KEY (toolissuetype, workflowdefectprojectfilter),"
         "CONSTRAINT fk_toolissuetype_workflowdefectprojectfilter__toolissuetype FOREIGN KEY (toolissuetype) "
         "REFERENCES toolissuetype (id),CONSTRAINT fk_toolissuetype_workflowdefectprojectfilter__workflowdefectpro "
         "FOREIGN KEY (workflowdefectprojectfilter) REFERENCES workflowdefectprojectfilter (id));"),

    step("CREATE INDEX IF NOT EXISTS idx_toolissuetype_workflowdefectprojectfilter ON "
         "public.toolissuetype_workflowdefectprojectfilter (workflowdefectprojectfilter);"),

    step("CREATE TABLE IF NOT EXISTS public.toolproject_workflow(toolproject integer NOT NULL,"
         "workflow integer NOT NULL,CONSTRAINT toolproject_workflow_pkey PRIMARY KEY (toolproject, workflow),"
         "CONSTRAINT fk_toolproject_workflow__toolproject FOREIGN KEY (toolproject) REFERENCES toolproject (id),"
         "CONSTRAINT fk_toolproject_workflow__workflow FOREIGN KEY (workflow) REFERENCES workflow (id));"),

    step("CREATE INDEX IF NOT EXISTS idx_toolproject_workflow ON public.toolproject_workflow (workflow);"),

    step("CREATE TABLE IF NOT EXISTS public.toolprojectcategory_workflow(toolprojectcategory integer NOT NULL,"
         "workflow integer NOT NULL,CONSTRAINT toolprojectcategory_workflow_pkey PRIMARY KEY "
         "(toolprojectcategory, workflow),CONSTRAINT fk_toolprojectcategory_workflow__toolprojectcategory "
         "FOREIGN KEY (toolprojectcategory) REFERENCES toolprojectcategory (id),"
         "CONSTRAINT fk_toolprojectcategory_workflow__workflow FOREIGN KEY (workflow) REFERENCES workflow (id));"),

    step("CREATE INDEX IF NOT EXISTS idx_toolprojectcategory_workflow ON "
         "public.toolprojectcategory_workflow (workflow);"),

    step("CREATE TABLE IF NOT EXISTS public.workflow_workflowdefectprojectfilter(workflow integer NOT NULL,"
         "workflowdefectprojectfilter integer NOT NULL,CONSTRAINT workflow_workflowdefectprojectfilter_pkey "
         "PRIMARY KEY (workflow, workflowdefectprojectfilter),CONSTRAINT "
         "fk_workflow_workflowdefectprojectfilter__workflow FOREIGN KEY (workflow) REFERENCES workflow (id),"
         "CONSTRAINT fk_workflow_workflowdefectprojectfilter__workflowdefectprojectf FOREIGN KEY "
         "(workflowdefectprojectfilter) REFERENCES workflowdefectprojectfilter (id));"),

    step("CREATE INDEX IF NOT EXISTS idx_workflow_workflowdefectprojectfilter ON "
         "public.workflow_workflowdefectprojectfilter (workflowdefectprojectfilter);"),

])

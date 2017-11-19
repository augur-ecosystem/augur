"""
add notifications
"""

from yoyo import step

__depends__ = {'__init__', 'augur_005.add-event-log-table.py'}

steps = [

    step("""
    ALTER TABLE workflow_workflowdefectprojectfilter ADD id SERIAL NOT NULL;
    ALTER TABLE workflow_workflowdefectprojectfilter DROP CONSTRAINT IF EXISTS workflow_workflowdefectprojectfilter_id_pk;
    ALTER TABLE workflow_workflowdefectprojectfilter ADD CONSTRAINT workflow_workflowdefectprojectfilter_id_pk PRIMARY KEY (id);
    """),
    step("""
    ALTER TABLE toolissuetype_workflowdefectprojectfilter ADD id SERIAL NOT NULL;
    ALTER TABLE toolissuetype_workflowdefectprojectfilter DROP CONSTRAINT IF EXISTS toolissuetype_workflowdefectprojectfilter_id_pk;
    ALTER TABLE toolissuetype_workflowdefectprojectfilter ADD CONSTRAINT toolissuetype_workflowdefectprojectfilter_id_pk PRIMARY KEY (id);
    """),

    step("""
    ALTER TABLE toolproject_workflow ADD id SERIAL NULL;
    ALTER TABLE toolproject_workflow DROP CONSTRAINT IF EXISTS toolproject_workflow_id_pk;
    ALTER TABLE toolproject_workflow ADD CONSTRAINT toolproject_workflow_id_pk PRIMARY KEY (id);    
    """),


    step("""
    ALTER TABLE toolissuetype_workflow ADD id SERIAL NOT NULL;
    ALTER TABLE toolissuetype_workflow DROP CONSTRAINT IF EXISTS toolissuetype_workflow_pkey;
    ALTER TABLE toolissuetype_workflow ADD CONSTRAINT toolissuetype_workflow_id_pk PRIMARY KEY (id);    
    """),

    step("""
    ALTER TABLE toolprojectcategory_workflow ADD id SERIAL NOT NULL;
    ALTER TABLE toolprojectcategory_workflow DROP CONSTRAINT IF EXISTS toolprojectcategory_workflow_pkey;
    ALTER TABLE toolprojectcategory_workflow ADD CONSTRAINT toolprojectcategory_workflow_id_pk PRIMARY KEY (id);    
    """),

    step("""
    ALTER TABLE toolissueresolution_workflow ADD id SERIAL NULL;
    ALTER TABLE toolissueresolution_workflow DROP CONSTRAINT IF EXISTS toolissueresolution_workflow_pkey;
    ALTER TABLE toolissueresolution_workflow ADD CONSTRAINT toolissueresolution_workflow_id_pk PRIMARY KEY (id);    
    """),


    step("""
ALTER TABLE public.toolissuestatus_workflow ADD id SERIAL NOT NULL;
ALTER TABLE public.toolissuestatus_workflow DROP CONSTRAINT IF EXISTS toolissuestatus_workflow_pkey;
ALTER TABLE public.toolissuestatus_workflow ADD CONSTRAINT toolissuestatus_workflow_id_pk PRIMARY KEY (id);    """),

]

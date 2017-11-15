""" Builds snippets from terraform's documentation """
import os
import re
import json
import yamldown
import mistune
from jinja2 import Template

NAME_REGEX = re.compile(r'`([a-z_]+)`')
OPTIONAL_REGEX = re.compile(r'[^(]+\((Optional)\)')
REQUIRED_REGEX = re.compile(r'[^(]+\((Required)\)')
DESCRIPTION_REGEX = re.compile(r'[^(]+\([^)]+\) (.*)')
SNIPPETS = dict()
SNIPPET_TEMPLATE = """{{object_type}} "{{name}}" "name" {
{% for argument in arguments -%}
    # {{ argument['text'] }}
    {{argument['name']}} = ""
{% endfor -%}
}
"""


def process_directory(object_type, prefix, files):
    """ Processes a single directory """
    for filename in files:
        filepath = "/".join([prefix, filename])
        with open(filepath, 'r') as f:
            (yml, markdown) = yamldown.load(f)

        if 'sidebar_current' in yml:
            snippet_name = yml['sidebar_current'][5:]
        else:
            snippet_name = yml['side_bar_current'][5:]
        resource_name = yml['page_title'].split()[-1]
        doc = process_documentation(markdown)
        arguments = doc.get('Argument Reference', [])
        description = doc['Description']

        SNIPPETS[snippet_name] = dict(
            prefix=snippet_name,
            description=description,
            body=generate_body(object_type, resource_name, arguments))


def process_documentation(markdown):
    """ Processes a markdown file """
    parsed = mistune.BlockLexer().parse(markdown)
    result = dict()
    current_heading = ''
    in_list_item = False
    current_item_text = []
    for item in parsed:
        if item['type'] == 'heading':
            if item['level'] == 1:
                current_heading = 'Description'
            else:
                current_heading = item['text']
            result[current_heading] = []
        elif item['type'] == 'loose_item_start':
            in_list_item = True
            current_item_text = []
        elif item['type'] == 'list_item_end':
            in_list_item = False
            result[current_heading].append(' '.join(current_item_text))
        elif 'text' in item and in_list_item:
            current_item_text.append(item['text'])
        elif 'text' in item:
            result[current_heading].append(item['text'])
    return result


def generate_body(object_type, resource_name, arguments):
    """ Generates a snipped body from the details """
    parsed_arguments = []
    for argument in arguments:
        if not NAME_REGEX.match(argument):
            continue
        try:
            result = dict()
            result['name'] = NAME_REGEX.match(argument)[1]
            # if result['name'] == 'name_regex':
            #     import ipdb; ipdb.set_trace()
            if OPTIONAL_REGEX.match(argument):
                result['optional'] = OPTIONAL_REGEX.match(argument)[1]
                if DESCRIPTION_REGEX.match(argument):
                    result['description'] = DESCRIPTION_REGEX.match(argument)[
                        1]
                else:
                    result['description'] = ''
            elif REQUIRED_REGEX.match(argument):
                result['optional'] = REQUIRED_REGEX.match(argument)[1]
                if DESCRIPTION_REGEX.match(argument):
                    result['description'] = DESCRIPTION_REGEX.match(argument)[
                        1]
                else:
                    result['description'] = ''
            else:
                result['optional'] = "Optional"
                result['description'] = argument.split(' - ')[-1]
            result['text'] = "{name} - ({optional}) {description}".format(
                **result)
            parsed_arguments.append(result)
        except Exception as e:
            import ipdb
            ipdb.set_trace()
            print(e)

    template_arguments = dict(
        object_type=object_type,
        name=resource_name,
        arguments=parsed_arguments,
    )
    return Template(SNIPPET_TEMPLATE).render(template_arguments)


for dirname, subdirlist, _filelist in os.walk('.'):
    if 'd' in subdirlist:
        process_directory('data', 'd', os.listdir('d'))
    if 'r' in subdirlist:
        process_directory('resource', 'r', os.listdir('r'))

print(json.dumps(SNIPPETS, indent=4, sort_keys=True))

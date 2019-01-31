#!/usr/bin/env python3
""" Builds snippets from terraform's documentation """
import os
import re
import json
import click
import yamldown
from yaml.parser import ParserError
from yaml.scanner import ScannerError
import mistune
from jinja2 import Template

NAME_REGEX = re.compile(r'`([a-z_]+)`')
OPTIONAL_REGEX = re.compile(r'[^(]+\((Optional)\)')
REQUIRED_REGEX = re.compile(r'[^(]+\((Required)\)')
DESCRIPTION_REGEX = re.compile(r'[^(]+\([^)]+\) (.*)')
SNIPPET_TEMPLATE = """{{object_type}} "{{name}}" "$1" {
{%- for argument in arguments %}
    # {{ argument['text'] }}
    {{argument['name']}} = ""
{% endfor %}
    # Exported Attributes
{%- for attribute in attributes %}
    # {{attribute}}
{%- endfor %}
}
"""


@click.command()
@click.argument('source', type=click.Path(exists=True))
@click.argument('target', type=click.Path(exists=True))
def build(source, target):
    """ Root command for click CLI tool """
    provider_list = os.listdir(source)
    for provider in provider_list:
        snippets = dict()
        provider_docs_dir = "{}/{}/website/docs".format(source, provider)
        for _dirname, subdirlist, _filelist in os.walk(provider_docs_dir):
            if 'd' in subdirlist:
                subdir = "{}/d".format(provider_docs_dir)
                process_directory('data', subdir, os.listdir(subdir), snippets)
            if 'r' in subdirlist:
                subdir = "{}/r".format(provider_docs_dir)
                process_directory('resource', subdir, os.listdir(subdir), snippets)
        target_file = "{target}/{provider}.json".format(
            target=target,
            provider=provider
        )
        with open(target_file, 'w') as f:
            print("Writing snippets for {provider} to {target_file}".format(
                target_file=target_file, provider=provider))
            f.write(json.dumps(snippets, indent=4, sort_keys=True))

def process_directory(object_type, prefix, files, snippets):
    """ Processes a single directory """
    for filename in files:
        filepath = "/".join([prefix, filename])
        try:
            with open(filepath, 'r') as f:
                (yml, markdown) = yamldown.load(f)
        except (ParserError, ScannerError):
            print('Error processing {}.'.format(filepath))

        if not yml:
            print('Error processing {}.'.format(filepath))
            continue

        if 'sidebar_current' in yml:
            snippet_name = yml['sidebar_current'][5:]
        else:
            snippet_name = yml['side_bar_current'][5:]

        resource_name = yml['page_title'].split()[-1]
        doc = process_documentation(markdown)
        arguments = doc.get('Argument Reference', [])
        description = ' '.join(doc['Description'])
        attributes = [x.replace('`', '"') for x
                      in doc.get('Attributes Reference', [])
                      if x.startswith('`')]
        snippets[snippet_name] = dict(
            prefix=snippet_name,
            description=description,
            body=generate_body(object_type, resource_name, arguments, attributes))


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


def generate_body(object_type, resource_name, arguments, attributes):
    """ Generates a snipped body from the details """
    parsed_arguments = []
    for argument in arguments:
        if not NAME_REGEX.match(argument):
            continue
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
        result['text'] = "{name} - ({optional}) {description}".format(**result)
        if result['optional'] == 'Optional':
            parsed_arguments.append(result)
        else:
            parsed_arguments.insert(0, result)

    template_arguments = dict(
        object_type=object_type,
        name=resource_name,
        arguments=parsed_arguments,
        attributes=attributes,
    )
    return Template(SNIPPET_TEMPLATE).render(template_arguments)

if __name__ == '__main__':
    build()
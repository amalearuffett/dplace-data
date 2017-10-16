#!/usr/bin/env python
# dplase_to_cldf.py - convert all datasets to csvw using pycldf

from __future__ import unicode_literals, print_function

import os
import collections

from six.moves import map

import attr
import clldutils.dsv
import pycldf.dataset

import pydplace.api

SRC = '..'
DST = '../cldf'
DIALECT = clldutils.dsv.Dialect()


def registered(cls):
    assert issubclass(cls, BaseConverter)
    try:
        seen = registered.converters
    except AttributeError:
        seen = registered.converters = []
    seen.append(cls)
    return cls


class BaseConverter(object):

    def skip(self, dataset):
        return False


Separator = collections.namedtuple('Separator', ['sep', 'split'])


class Converter(BaseConverter):

    def __init__(self):
        fields = attr.fields(self._source_cls)
        columns = list(self._itercols(fields, self._convert))

        def extract(s):
            return {target: trans(getattr(s, name))
                    for name, trans, target, _ in columns}

        self._extract = extract
        self._add_component_args = ([self._component] +
                                    [args for _, _, _, args in columns])

    @staticmethod
    def _itercols(fields, convert):
        for f in fields:
            name = f.name
            if name in convert:
                args = convert[name]
                if args is None:
                    continue
                elif hasattr(args, 'setdefault'):
                    target = args.setdefault('name', name)
                else:
                    target = args
                    args = {'name': target}
            else:
                args = {'name': name}
                target = name

            transform = lambda x: x
            if 'separator' in args:
                sep, split = args['separator']
                args['separator'] = sep
                if split:
                    transform = lambda x: x.split(sep)

            if 'datatype' not in args:
                args['datatype'] = 'float' if f.convert is float else 'string'

            yield name, transform, target, args

    def __call__(self, dataset):
        component = self._component.get('dc:conformsTo', self._component['url'])
        items = map(self._extract, self._iterdata(dataset))
        write_kwargs = {component: items}
        # FIXME: pycldf.dataset.add_component mutates component dict
        import copy
        return copy.deepcopy(self._add_component_args), write_kwargs


class SkipMixin(object):

    def skip(self, dataset, _sentinel=object()):
        return next(iter(self._iterdata(dataset)), _sentinel) is _sentinel


@registered
class LanguageTable(SkipMixin, Converter):

    _source_cls = pydplace.api.Society

    _iterdata = staticmethod(lambda dataset: dataset.societies)

    _component = {
        'url': 'societies.csv',
        'dc:conformsTo': 'http://cldf.clld.org/v1.0/terms.rdf#LanguageTable',
        'tableSchema': {'primaryKey': ['id']},
    }

    _convert = {
        'id': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#id',
            'required': True,
        },
        'xd_id': {
            'required': True,
            'datatype': {'base': 'string', 'format': r'xd\d+'},
        },
        'pref_name_for_society': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#name',
            'required': True,
        },
        'glottocode': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#glottocode',
            'required': True,
        },
        'ORIG_name_and_ID_in_this_dataset': {
            'required': True,
        },
        'alt_names_by_society': {
            'separator': Separator(', ', split=True)
        },
        'main_focal_year': {
            'datatype': 'integer',
            'required': True,
        },
        'HRAF_name_ID': {
            'datatype': {'base': 'string', 'format': r'.+ \([A-Z0-9]+\)'},
        },
        'HRAF_link': {
            'datatype': {'base': 'string', 'format': r':http://.+|in process'},
        },
        'origLat': {
            'datatype': {'base': 'decimal', 'minimum': -90, 'maximum': 90},
            'required': True,
        },
        'origLong': {
            'datatype': {'base': 'decimal', 'minimum': -180, 'maximum': 180},
            'required': True,
        },
        'Lat': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#latitude',
            'datatype': {'base': 'decimal', 'minimum': -90, 'maximum': 90},
            'required': True,
        },
        'Long': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#longitude',
            'datatype': {'base': 'decimal', 'minimum': -180, 'maximum': 180},
            'required': True,
        },
        'Comment': {'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#comment'},
    }


@registered
class LangugageRelatedTable(SkipMixin, Converter):

    _source_cls = pydplace.api.RelatedSocieties

    _iterdata = staticmethod(lambda dataset: dataset.society_relations)

    _component = {
        'url': 'societies_mapping.csv',
        'tableSchema': {
            'primaryKey': ['id'],
            'foreignKeys': [
                {'columnReference': 'id',
                'reference': {'resource': 'societies.csv', 'columnReference': 'id'}},
            ],
        },
    }

    _convert = {
        'id': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#id',
            'required': True,
        },
        'related': {
            'separator': Separator('; ', split=False),
        },
    }


@registered
class ParameterTable(Converter):

    _source_cls = pydplace.api.Variable

    _iterdata = staticmethod(lambda dataset: dataset.variables)

    _component = {
        'url': 'variables.csv',
        'dc:conformsTo': 'http://cldf.clld.org/v1.0/terms.rdf#ParameterTable',
        'tableSchema': {'primaryKey': ['id']}
    }

    _convert = {
        'id': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#id',
            'required': True,
        },
        'category': {
            'separator': Separator(', ', split=False),
            'required': True,
        },
        'title': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#name',
            'required': True,
        },
        'definition': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#description',
            'required': True,
        },
        'type': {
            'datatype': {
                'base': 'string',
                'format': r'Categorical|Ordinal|Continuous',
            },
            'required': True,
        },
        'source': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source',
            'required': True,
        },
        'notes': {'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#comment'},
        'codes': None,
    }


@registered
class CodeTable(SkipMixin, BaseConverter):

    _component = {
        'url': 'codes.csv',
        'dc:conformsTo': 'http://cldf.clld.org/v1.0/terms.rdf#CodeTable',
        'tableSchema': {
            'primaryKey': ['var_id', 'code'],
            'foreignKeys': [
                {'columnReference': 'var_id',
                'reference': {'resource': 'variables.csv', 'columnReference': 'id'}},
            ],
        },
    }

    _convert = {
        'var_id': {
            'name': 'var_id',
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#parameterReference',
            'required': True,
        },
        'code': {
            'name': 'code',
            'datatype': {'base': 'string', 'format': r'\d+|NA'},
            'required': True,
        },
        'description': {
            'name': 'description',
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#description',
            'required': True,
        },
        'name': {
            'name': 'name',
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#name',
            'required': True,
        },
    }

    _iterdata = staticmethod(lambda dataset: (c for v in dataset.variables for c in v.codes))

    def __call__(self, dataset):
        codes = list(self._iterdata(dataset))
        add_component_args = ([self._component] +
                              [self._convert.get(f, f) for f in codes[0]._fields])
        component = self._component.get('dc:conformsTo', self._component['url'])
        items = (c._asdict() for c in codes)
        write_kwargs = {component: items}
        # FIXME: pycldf.dataset.add_component mutates component dict
        import copy
        return copy.deepcopy(add_component_args), write_kwargs


@registered
class ValueTable(Converter):

    _source_cls = pydplace.api.Data

    _component = {
        'url': 'data.csv',
        'dc:conformsTo': 'http://cldf.clld.org/v1.0/terms.rdf#ValueTable',
        'tableSchema': {
            'primaryKey': ['soc_id', 'sub_case', 'year', 'var_id', 'code', 'references'],
            'foreignKeys': [
                {'columnReference': 'soc_id',
                'reference': {'resource': 'societies.csv', 'columnReference': 'id'}},
                {'columnReference': ['var_id', 'code'],
                'reference': {'resource': 'codes.csv', 'columnReference': ['var_id', 'code']}},
            ],
        },
    }

    _convert = {
        # FIXME: requires id
        'soc_id': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#languageReference',
            'required': True,
        },
        'sub_case': {
            'null': None,
            'required': True,
        },
        'year': {
            'datatype': {'base': 'string', 'format': r'(?:\d+(?:-\d+)?)?'},
            'null': None,
            'required': True,
        },
        'var_id': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#parameterReference',
            'required': True,
        },
        'code': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#codeReference',
            'datatype': CodeTable._convert['code']['datatype'],
            'required': True,
        },
        'comment': {'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#comment'},
        'references': {
            'propertyUrl': 'http://cldf.clld.org/v1.0/terms.rdf#source',
            'separator': Separator('; ', split=False),
            'null': None,
            'required': True,
        },
    }

    _iterdata = staticmethod(lambda dataset: dataset.data)


def main(source_dir=SRC, dest_dir=DST, dialect=DIALECT):
    repo = pydplace.api.Repos(source_dir)

    if not os.path.exists(dest_dir):
        os.mkdir(dest_dir)

    converters = [cls() for cls in registered.converters]

    for d in repo.datasets:
        print(d)
        result_dir = os.path.join(dest_dir, d.id)
        result = pycldf.dataset.StructureDataset.in_dir(result_dir)
        del result.tables[:]  # FIXME
        result.tablegroup.dialect = dialect
        final_write_kwargs = {}
        for conv in converters:
            if not conv.skip(d):
                add_args, write_kwargs = conv(d)
                result.add_component(*add_args)
                final_write_kwargs.update(write_kwargs)
        result.write(**final_write_kwargs)


if __name__ == '__main__':
    main()

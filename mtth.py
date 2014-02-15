#!/usr/bin/env python

"""build script for mtth.org"""

from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import glob
import iso8601
import markdown
import os
import shutil
import subprocess
import sys
import uuid


INPUT_DIR = 'source'
OUTPUT_DIR = 'output'
TEMPLATES_DIR = 'templates'


IMAGE_SIZE = "600x600"
POSTS_PER_PAGE = 5
SECTION_SEPARATOR = '---\n'

jinja2_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


class Post(object):

    def __init__(self, filename):
        self.filename = filename
        contents = open(self.filename).read()
        chunks = contents.split(SECTION_SEPARATOR)

        if len(chunks) == 2:
            header, body = chunks
            self.meta = self.read_header(header)
            self.excerpt = body
            self.body = body
            self.has_excerpt = False

        if len(chunks) == 3:
            header, excerpt, body = chunks
            self.meta = self.read_header(header)
            self.excerpt = excerpt
            self.body = body
            self.has_excerpt = True

        self.meta = self.read_header(header)

    def read_header(self, header_text):
        pairs = [line.split(": ", 1) for line in header_text.split('\n') if line]
        return {key.strip(): value.strip() for key, value in pairs}

    def timestamp(self):
        return iso8601.parse_date(self.meta['timestamp'])

    def rendered_excerpt(self):
        return markdown.markdown(self.excerpt.strip())

    def rendered_body(self):
        return markdown.markdown(self.body.strip())

    def slug(self):
        return self.filename.replace('%s/' % INPUT_DIR, '').replace('.md', '')

    def title(self):
        return self.meta.get('title', self.slug())

    def url(self):
        return '/%s/' % self.slug()

    def write_output(self):
        output_dir = '%s/%s' % (OUTPUT_DIR, self.slug())
        index_filename = "%s/index.html" % output_dir
        os.makedirs(output_dir)
        template = jinja2_env.get_template('post.html')
        with open(index_filename, 'w') as output_file:
            output = template.render(post=self)
            output_file.write(output)
            print 'Created file "%s"' % index_filename


class StaticFile(object):

    def __init__(self, filename):
        self.filename = filename

    def output_filename(self):
        return self.filename.replace(INPUT_DIR, OUTPUT_DIR)

    def copy(self):
        shutil.copyfile(self.filename, self.output_filename())
        print 'Copied file "%s"' % self.filename


def _chunks(l, n):
    return [l[i:i+n] for i in range(0, len(l), n)]


def _listdir():
    return [filename for filename in glob.glob('%s/*' % INPUT_DIR)]


def _clean():
    subprocess.call("rm -rf ./%s/*" % OUTPUT_DIR, shell=True)
    print 'Removed contents of directory "%s"' % OUTPUT_DIR


def _write_indexes(posts):
    chunks = _chunks(posts, POSTS_PER_PAGE)
    for index, chunk in enumerate(chunks, 1):
        output_dir = "%s/%s" % (OUTPUT_DIR, index)
        os.makedirs(output_dir)
        output_filename = "%s/index.html" % output_dir

        if index == 1:
            previous_url = None
        elif index == 2:
            previous_url = "/"
        else:
            previous_url = "/%s/" % (index - 1)

        if index == len(chunks):
            next_url = None
        else:
            next_url = "/%s/" % (index + 1)

        template = jinja2_env.get_template('list.html')
        with open(output_filename, 'w') as output_file:
            output = template.render(posts=chunk, previous_url=previous_url, next_url=next_url, page_number=index)
            output_file.write(output)
        print 'Created file "%s"' % output_filename
    first_index_filename = "%s/1/index.html" % OUTPUT_DIR
    root_index_filename = "%s/index.html" % OUTPUT_DIR
    shutil.copyfile(first_index_filename, root_index_filename)
    print 'Copied "%s" to "%s"' % (first_index_filename, root_index_filename)


def new(content=None):
    filename = "%s.md" % uuid.uuid4().hex[:6]
    timestamp = datetime.utcnow().isoformat()
    content = content or "# Hello, world"
    with open("%s/%s" % (INPUT_DIR, filename), 'w') as new_file:
        new_file.write("timestamp: %s\n---\n\n%s" % (timestamp, content))
    print 'Created new file "%s"' % filename


def build():
    _clean()
    filenames = _listdir()

    posts = []
    other = []

    for filename in filenames:
        if filename.endswith('.md'):
            posts.append(Post(filename))
        else:
            other.append(StaticFile(filename))

    posts = sorted(posts, key=lambda post: post.timestamp(), reverse=True)

    for post in posts:
        post.write_output()

    for item in other:
        item.copy()

    _write_indexes([post for post in posts if not post.meta.get('exclude_from_list')])


def import_image():
    """Brittle, but whatever"""
    name_or_url = sys.argv[2]
    extension = name_or_url.rsplit('.', 1)[-1]
    slug = uuid.uuid4().hex[:6]
    target_filename = "%s.%s" % (slug, extension)
    target_path = "%s/%s.%s" % (INPUT_DIR, slug, extension)

    if name_or_url.startswith('http'):
        subprocess.call("curl %s > %s" % (name_or_url, target_path), shell=True)
    else:
        shutil.copyfile(name_or_url, target_path)

    print 'Created file "%s"' % target_path

    subprocess.call("convert %s -resize %s %s" % (target_path, IMAGE_SIZE, target_path), shell=True)
    print "Resized to fit %s" % IMAGE_SIZE

    new(content="![%s](/%s)" % (slug, target_filename))


COMMANDS = {
    'new': new,
    'build': build,
    'import': import_image,
}


def main():
    if len(sys.argv) == 1:
        exit("Usage: mtth <%s>" % "|".join(COMMANDS.keys()))

    command = sys.argv[1]

    try:
        COMMANDS[command]()
    except KeyError:
        exit("%s is not a supported command. \n\n%s" % (command, __doc__))


if __name__ == "__main__":
    main()

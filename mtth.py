#!/usr/bin/env python

"""build script for mtth.org"""

from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import glob
import iso8601
import markdown
import os
import re
import shutil
import subprocess
import sys
import uuid


INPUT_DIR = 'source'
OUTPUT_DIR = 'output'
TEMPLATES_DIR = 'templates'


IMAGE_SIZE = "1000x1000"
POSTS_PER_PAGE = 5
SECTION_SEPARATOR = '---\n'

H1_RE = re.compile("<h1>(.*)</h1>")

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
        self._rendered_excerpt = None
        self._rendered_body = None

    def read_header(self, header_text):
        pairs = [line.split(": ", 1) for line in header_text.split('\n') if line]
        return {key.strip(): value.strip() for key, value in pairs}

    def timestamp(self):
        return iso8601.parse_date(self.meta['timestamp'])

    def body_classes(self):
        return self.meta.get('body_classes')

    def rendered_excerpt(self):
        if not self._rendered_excerpt:
            self._rendered_excerpt = markdown.markdown(self.excerpt.strip())
        return self._rendered_excerpt

    def rendered_body(self):
        if not self._rendered_body:
            self._rendered_body = markdown.markdown(self.body.strip())
        return self._rendered_body

    def slug(self):
        return self.filename.replace('%s/' % INPUT_DIR, '').replace('.md', '')

    def title(self):
        title = self.meta.get('title')
        if title:
            return title

        title = self.find_title_in_html(self.rendered_excerpt())
        if title:
            return title

        title = self.find_title_in_html(self.rendered_body())
        if title:
            return title

        return self.slug()

    def find_title_in_html(self, html):
        match = H1_RE.search(html)
        if match:
            return match.groups()[0]

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


def _write_feed(posts):
    output_filename = "%s/feed.atom" % OUTPUT_DIR
    template = jinja2_env.get_template('feed.atom')
    with open(output_filename, 'w') as output_file:
        output = template.render(posts=posts)
        output_file.write(output)
    print 'Created file "%s"' % output_filename


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

    posts_excluding_pages = [post for post in posts if not post.meta.get('exclude_from_list')]
    _write_indexes(posts_excluding_pages)
    _write_feed(posts_excluding_pages)


def import_images():
    """Brittle, but whatever"""

    for name_or_url in sys.argv[2:]:
        extension = name_or_url.rsplit('.', 1)[-1]
        slug = uuid.uuid4().hex[:6]
        target_filename = "%s.%s" % (slug, extension)
        target_path = "%s/%s.%s" % (INPUT_DIR, slug, extension)

        if name_or_url.startswith('http'):
            subprocess.call("curl %s > %s" % (name_or_url, target_path), shell=True)
        else:
            name_or_url = os.path.expanduser(name_or_url)
            shutil.copyfile(name_or_url, target_path)

        subprocess.call("convert %s -resize %s %s" % (target_path, IMAGE_SIZE, target_path), shell=True)

        print "![%s](/%s)" % (slug, target_filename)


COMMANDS = {
    'new': new,
    'build': build,
    'import': import_images,
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

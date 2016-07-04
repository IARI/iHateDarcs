from abc import *


class Injector(ABCMeta):
    # INJECT_MAPPINGS = []

    def __new__(cls, name, bases, dct):
        # print('creating {}'.format(name))
        ownbases, others = Injector.divide(*bases, test=Injector.subclasstest)
        # print('own: {}'.format(ownbases))
        # print('oth: {}'.format(others))

        if not ownbases:
            class Base:
                INJECT_MAPPING = []

                @classmethod
                def inject(cls, obj):
                    #print("injecting {}".format(obj))
                    if isinstance(obj, Base):
                        return obj

                    for SourceType, InjectorType in cls.INJECT_MAPPING:
                        if isinstance(obj, SourceType):
                            return InjectorType(obj)

                    raise TypeError('cannot inject values of type {} (val: {})'.format(type(obj), obj))

                @classmethod
                def associate(cls, typ):
                    cls.INJECT_MAPPING.append((typ, cls))

            bases += (Base,)

        productClass = super(Injector, cls).__new__(cls, name, bases, dct)

        if ownbases:
            for b in others:
                productClass.INJECT_MAPPING.append((b, productClass))

        return productClass

    @classmethod
    def divide(cls, *args, test):
        first = []
        second = []
        for a in args:
            (first if test(a) else second).append(a)
        return first, second

    @classmethod
    def subclasstest(cls, c):
        r = issubclass(type(c), cls)
        # print('{} {}subof {}'.format(c, '=' if r else '!', cls))
        return r

        # @classmethod
        # def inject(cls, obj):
        #     for SourceType, InjectorType in cls.INJECT_MAPPINGS:
        #         if isinstance(obj, SourceType):
        #             return InjectorType(obj)
        #
        #     raise TypeError('cannot inject values of type {} (val: {})'.format(type(obj), obj))

# class testinj(metaclass=Injector):
#     pass
#
#
# class testinjInhA(testinj):
#     pass
#
#
# class testinjInhB(testinj, str):
#     pass
#
#
# class testinjInhC(testinj, list):
#     pass
#
#
# class testinjInhD(testinjInhB, testinjInhA):
#     pass
